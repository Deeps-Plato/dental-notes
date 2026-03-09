# Phase 2: Clinical Extraction - Research

**Researched:** 2026-03-08
**Domain:** Local LLM integration (Ollama + Qwen3) for dental SOAP note extraction
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 adds the clinical intelligence layer: a local LLM (Ollama with Qwen3) processes the accumulated transcript from Phase 1, filters chitchat, structures clinical content into a dental SOAP note with CDT codes, and re-attributes speaker labels using conversational context. The key technical challenge is GPU memory management -- Qwen3 8B (5.2GB model weights at Q4_K_M) requires ~6-7GB VRAM which *does not fit* alongside Whisper on a GTX 1050 (4GB) and barely fits alone. The architecture must support sequential model loading (unload Whisper before loading LLM) and a fallback to Qwen3 4B (~2.5GB at Q4_K_M) for 4GB VRAM hardware.

The Ollama Python client (`ollama` v0.6.1) provides both sync and async clients with native structured output support via Pydantic JSON schemas. This is the correct integration path -- define a `SoapNote` Pydantic model, pass its schema to the `format` parameter, and Ollama constrains the LLM to produce valid JSON matching that schema. No custom JSON parsing needed.

**Primary recommendation:** Use `ollama` Python package v0.6.1 with Pydantic-based structured outputs, Qwen3 8B as the default model (4B fallback for 4GB GPUs), sequential GPU loading via `keep_alive=0` to free VRAM between Whisper and LLM, and an embedded CDT code reference list in the system prompt for accurate code suggestions.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Ollama for local LLM hosting -- no cloud APIs, no patient data transmitted
- Qwen3 8B as the target model -- fits in 8GB VRAM alongside or sequentially with Whisper
- Sequential GPU loading: Whisper and LLM cannot coexist in VRAM on GTX 1050 (4GB) -- must unload Whisper before loading LLM, or use CPU fallback
- GTX 1070 Ti (8GB) is the common hardware -- may support both models simultaneously
- Input: plain-text transcript with keyword-based speaker labels from Phase 1
- Output: structured SOAP note (Subjective, Objective, Assessment, Plan) + CDT codes
- Chitchat filtering: LLM identifies and removes social conversation, keeping only clinically relevant content
- CDT code suggestions: extracted from the Assessment and Plan sections of the SOAP note
- Phase 1's keyword classifier misidentifies doctor speech when doctor pauses mid-thought
- LLM must re-attribute speaker labels using conversational context
- The LLM pass produces final speaker labels; keyword labels are a real-time preview only
- All LLM inference runs locally via Ollama -- PRV-01 still applies
- No Ollama cloud features, no model telemetry
- Transcript data stays in memory during processing, not written to additional files
- Test file before implementation file
- Integration test mandatory: prove transcript -> LLM -> SOAP note pipeline works end-to-end
- Human verification checkpoint: user must confirm SOAP note quality from a real dental transcript
- No mocking away the LLM -- use real Ollama in integration tests (or a realistic fake that validates prompt/response structure)

### Claude's Discretion
- Prompt engineering for the SOAP note extraction (system prompt, few-shot examples, output format)
- How to handle the Whisper->LLM GPU handoff (sequential loading vs CPU fallback)
- Ollama client library choice (ollama-python, httpx to Ollama REST API, or subprocess)
- Whether to process the full transcript at once or in sections
- CDT code lookup strategy (embedded list vs prompted knowledge)
- Error handling when Ollama is not running or model not pulled

### Deferred Ideas (OUT OF SCOPE)
- Multi-model comparison (try different local LLMs and compare quality) -- v2+ optimization
- Streaming LLM output (show SOAP note building in real-time) -- Phase 3 UI concern
- Appointment-type templates (exam vs restorative vs hygiene) -- v2 requirement ENH-01
- Speaker diarization from audio features -- v2 requirement ENH-02

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-01 | Local LLM filters clinical content from social conversation/chitchat | Ollama structured output with Pydantic model; system prompt instructs LLM to separate clinical from social content; Qwen3 8B has sufficient reasoning capability |
| CLI-02 | Filtered content is structured into a dental SOAP note (Subjective, Objective, Assessment, Plan) | Pydantic `SoapNote` model with four sections enforced via `format` parameter; dental-specific system prompt with few-shot example |
| CLI-03 | CDT procedure codes are suggested from the Assessment/Plan sections | Embedded CDT code reference (~50 common codes) in system prompt; Pydantic model includes `cdt_codes` field with code+description pairs |
| CLI-04 | LLM re-attributes speaker labels using conversational context | Dedicated prompt pass (or combined pass) that analyzes turn-taking patterns, instruction-giving vs symptom-reporting, continuity across pauses |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ollama` | 0.6.1 | Python client for Ollama REST API | Official library; uses httpx internally; sync+async; native structured output support via format parameter |
| Qwen3 8B (Q4_K_M) | Latest via `ollama pull qwen3:8b` | Clinical text processing LLM | 5.2GB download; fits in 8GB VRAM; strong reasoning; Apache 2.0 license; supports thinking/non-thinking modes |
| Qwen3 4B (Q4_K_M) | Latest via `ollama pull qwen3:4b` | Fallback LLM for 4GB VRAM | 2.5GB download; fits in 4GB VRAM with context; Qwen3 4B reportedly rivals Qwen2.5-72B quality |
| `pydantic` | 2.x (already installed via pydantic-settings) | Structured output schema definition | Already a dependency; `model_json_schema()` generates JSON schema for Ollama format parameter |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | 0.27+ (already dev dep) | HTTP client for Ollama health checks | Already installed; use for connectivity checks before LLM calls |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ollama` Python package | Raw `httpx` to REST API | More control but must handle response parsing, streaming, error codes manually -- not worth it |
| `ollama` Python package | `subprocess` calling `ollama run` | No structured output, must parse stdout, error handling is fragile |
| `ollama` Python package | `langchain-ollama` | Heavy dependency for a simple use case; LangChain adds complexity without value here |
| Qwen3 8B | Llama 3.1 8B | Qwen3 has better multilingual support and thinking modes; both are comparable for English clinical text |

**Installation:**
```bash
pip install ollama>=0.6.1
```

Add to `pyproject.toml` dependencies:
```toml
"ollama>=0.6.1",
```

## Architecture Patterns

### Recommended Project Structure
```
src/dental_notes/
  clinical/              # NEW - Phase 2 module
    __init__.py
    ollama_service.py    # OllamaService: model management, health check, generate
    extractor.py         # ClinicalExtractor: transcript -> SOAP note pipeline
    speaker.py           # SpeakerReattributor: LLM-based speaker label correction
    prompts.py           # System prompts, few-shot examples, CDT reference
    models.py            # Pydantic models: SoapNote, CdtCode, ExtractionResult
  config.py              # Extended with Ollama settings
  session/
    manager.py           # Extended with extract_note() method or hook
```

### Pattern 1: Pydantic Structured Output with Ollama
**What:** Define output schema as Pydantic model, pass schema to Ollama, validate response
**When to use:** Every LLM call that needs structured output (SOAP note, speaker labels)
**Example:**
```python
# Source: Ollama docs + ollama-python structured outputs documentation
from pydantic import BaseModel
from ollama import Client

class CdtCode(BaseModel):
    code: str        # e.g., "D2391"
    description: str # e.g., "Posterior composite, 1 surface"

class SoapNote(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str
    cdt_codes: list[CdtCode]

client = Client(host="http://localhost:11434")
response = client.chat(
    model="qwen3:8b",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": transcript_text},
    ],
    format=SoapNote.model_json_schema(),
    options={"temperature": 0, "num_ctx": 8192},
)
note = SoapNote.model_validate_json(response.message.content)
```

### Pattern 2: Sequential GPU Model Loading
**What:** Unload Whisper before loading LLM, unload LLM before reloading Whisper
**When to use:** Always on 4GB VRAM; optionally on 8GB VRAM
**Example:**
```python
# Source: Ollama API docs, keep_alive parameter
# Step 1: Unload Whisper (already in WhisperService)
whisper_service.unload()  # del self._model; frees VRAM
import gc; gc.collect()
import torch; torch.cuda.empty_cache()

# Step 2: Run LLM inference (Ollama manages its own GPU)
result = ollama_service.extract_soap_note(transcript)

# Step 3: Unload LLM model from Ollama
client.chat(model="qwen3:8b", messages=[], keep_alive=0)

# Step 4: Reload Whisper for next session
whisper_service.load_model()
```

### Pattern 3: Service Layer with Health Checks
**What:** OllamaService wraps the ollama client with connectivity and model availability checks
**When to use:** Before any LLM call
**Example:**
```python
# Source: ollama-python docs, error handling patterns
import ollama
from ollama import Client, ResponseError

class OllamaService:
    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen3:8b"):
        self._client = Client(host=host)
        self._model = model

    def is_available(self) -> bool:
        """Check if Ollama server is running and model is pulled."""
        try:
            models = self._client.list()
            return any(m.model.startswith(self._model) for m in models.models)
        except Exception:
            return False

    def ensure_model(self) -> None:
        """Pull model if not available."""
        try:
            self._client.show(self._model)
        except ResponseError as e:
            if e.status_code == 404:
                self._client.pull(self._model)
            else:
                raise

    def unload_model(self) -> None:
        """Free GPU memory by unloading model."""
        self._client.chat(model=self._model, messages=[], keep_alive=0)
```

### Pattern 4: Thinking Mode Control for Qwen3
**What:** Disable Qwen3's "thinking" mode for faster, more deterministic output
**When to use:** Always for SOAP note extraction (thinking mode adds latency and verbose internal reasoning)
**Example:**
```python
# Source: Ollama docs, Qwen3 GitHub, community reports
# Method: Add /nothink to user message or use system prompt instruction
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": f"/nothink\n\n{transcript_text}"},
]
# Alternative: set temperature=0 which implicitly reduces thinking verbosity
```

### Anti-Patterns to Avoid
- **Mocking away Ollama in all tests:** The TDD methodology requires integration tests with real Ollama (or a realistic fake that validates prompt/response structure). Unit tests can mock the OllamaService, but at least one integration test must hit real Ollama.
- **Processing transcript in tiny sections:** The LLM needs full conversational context for accurate speaker re-attribution and chitchat filtering. Process the entire transcript in a single call (dental appointments are 10-30 min, typically <4000 tokens of transcript).
- **Hardcoding model name without fallback:** Must support both `qwen3:8b` (8GB GPU) and `qwen3:4b` (4GB GPU) via configuration.
- **Leaving LLM model loaded in VRAM indefinitely:** Use `keep_alive=0` after extraction to free VRAM for the next transcription session.
- **Using Ollama cloud/telemetry features:** Violates PRV-01. Ensure `OLLAMA_NOPRUNE=1` and no cloud model references.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON output from LLM | Custom regex parsing of LLM text output | Ollama structured output + Pydantic schema validation | LLMs produce inconsistent JSON without grammar constraints; Ollama's format parameter uses constrained decoding |
| HTTP client for Ollama API | Raw `urllib` or `requests` calls | `ollama` Python package (uses httpx internally) | Handles streaming, error codes, response types, model management endpoints |
| CDT code validation | Custom lookup table with fuzzy matching | Embedded reference list in system prompt + Pydantic validation | The LLM itself knows common CDT codes; the reference list improves accuracy; Pydantic validates the structure |
| GPU memory management | Manual CUDA memory tracking | Ollama's `keep_alive` parameter + WhisperService.unload() | Ollama manages its own CUDA context; WhisperService already has unload(); combining both handles the handoff |
| Prompt template engine | Jinja2 or f-string template system | Plain Python string constants in `prompts.py` | Prompts are static (no loops/conditionals); a template engine adds complexity without value |

**Key insight:** Ollama's structured output feature (JSON schema via `format` parameter) is the single most important capability for this phase. It eliminates the fragile "parse LLM text output" pattern that causes most LLM integration failures.

## Common Pitfalls

### Pitfall 1: VRAM Exhaustion on GTX 1050
**What goes wrong:** Qwen3 8B Q4_K_M needs ~6-7GB VRAM. GTX 1050 has 4GB. Loading the model fails or spills to CPU RAM, causing 5-30x slowdown.
**Why it happens:** CONTEXT.md says "Qwen3 8B fits in 8GB VRAM alongside or sequentially with Whisper" but does not account for the 4GB minimum hardware.
**How to avoid:** Default to `qwen3:4b` on 4GB GPUs, `qwen3:8b` on 8GB+ GPUs. Detect available VRAM at startup (Ollama reports this). Add `ollama_model` setting to config with auto-detection logic.
**Warning signs:** Ollama logs showing "offloading N layers to CPU"; generation speed <5 tokens/sec.

### Pitfall 2: Context Window vs Transcript Length
**What goes wrong:** Long appointments (30+ min) produce transcripts that exceed the context window, causing truncation and lost clinical data.
**Why it happens:** Qwen3's default context is 40K tokens but VRAM for KV cache grows linearly. At 32K context, KV cache alone needs ~3GB.
**How to avoid:** Limit `num_ctx` to 8192 for 4GB GPUs, 16384 for 8GB GPUs. A 30-minute dental appointment produces roughly 3000-5000 words (~4000-6500 tokens), which fits in 8K context with system prompt. Monitor token count before submission.
**Warning signs:** Truncated SOAP notes missing content from early in the appointment.

### Pitfall 3: Qwen3 Thinking Mode Polluting Output
**What goes wrong:** Qwen3 includes `<think>...</think>` blocks in its response, which break JSON parsing even with structured output.
**Why it happens:** Qwen3's hybrid thinking mode is enabled by default and may activate on complex prompts.
**How to avoid:** Add `/nothink` to user messages or use `--think=false` via Modelfile. Test with thinking mode both on and off. The structured output format parameter *should* suppress thinking blocks, but verify.
**Warning signs:** Response contains `<think>` tags; Pydantic validation fails on response content.

### Pitfall 4: Ollama Not Running or Model Not Pulled
**What goes wrong:** The app crashes or hangs when Ollama isn't running (connection refused) or the model hasn't been pulled yet (404).
**Why it happens:** Ollama is a separate service that must be running. The model must be downloaded first (~5GB).
**How to avoid:** Add health check at startup (`OllamaService.is_available()`). Provide clear error messages: "Ollama is not running -- start it with `ollama serve`" or "Model qwen3:8b is not installed -- run `ollama pull qwen3:8b`". Do NOT auto-pull in production (5GB download during a patient visit is unacceptable).
**Warning signs:** `httpx.ConnectError` or `ollama.ResponseError` with status 404.

### Pitfall 5: Speaker Re-Attribution Losing Chunk Boundaries
**What goes wrong:** LLM re-attributes speakers but returns a flat text without preserving the original chunk boundaries, making it impossible to map back to the UI's chunk-based display.
**Why it happens:** The LLM processes the full transcript and may restructure it.
**How to avoid:** Include chunk indices in the input format and require them in the output schema. Example: `[{"chunk_id": 0, "speaker": "Doctor", "text": "..."}]`. The Pydantic model enforces this structure.
**Warning signs:** Returned chunk count differs from input chunk count; UI shows misaligned text.

### Pitfall 6: CDT Code Hallucination
**What goes wrong:** LLM invents non-existent CDT codes (e.g., "D9999") or assigns wrong codes to procedures.
**Why it happens:** LLM general knowledge of CDT codes is imprecise; codes change yearly.
**How to avoid:** Embed a curated reference list of ~50 common CDT codes in the system prompt. Instruct the LLM to ONLY use codes from the reference list. Add Pydantic validation that checks code format (D followed by 4 digits). Accept that this is a *suggestion* -- the dentist reviews and corrects in Phase 3.
**Warning signs:** Codes not matching any known CDT code; descriptions that don't match the code.

## Code Examples

Verified patterns from official sources:

### Pydantic Models for SOAP Note Output
```python
# Source: Application-specific, using Pydantic v2 patterns
from pydantic import BaseModel, Field

class CdtCode(BaseModel):
    """A CDT dental procedure code suggestion."""
    code: str = Field(pattern=r"^D\d{4}$", description="CDT code, e.g. D2391")
    description: str = Field(description="Procedure description")

class SpeakerChunk(BaseModel):
    """A re-attributed transcript chunk."""
    chunk_id: int
    speaker: str = Field(description="Doctor or Patient")
    text: str

class SoapNote(BaseModel):
    """Structured dental SOAP note."""
    subjective: str = Field(description="Chief complaint, patient-reported symptoms")
    objective: str = Field(description="Clinical findings, tooth numbers, conditions")
    assessment: str = Field(description="Diagnoses with tooth numbers, classification")
    plan: str = Field(description="Procedures planned, materials, next visit")
    cdt_codes: list[CdtCode] = Field(description="Suggested CDT codes from plan")

class ExtractionResult(BaseModel):
    """Complete output from clinical extraction."""
    soap_note: SoapNote
    speaker_chunks: list[SpeakerChunk]
    clinical_summary: str = Field(description="One-sentence summary of the visit")
```

### System Prompt for SOAP Note Extraction
```python
# Source: Domain expertise + prompt engineering best practices
SYSTEM_PROMPT = """You are a dental clinical note assistant. You process transcripts
from dental appointments and produce structured SOAP notes.

## Your Task
1. Read the transcript of a dental appointment between Doctor and Patient.
2. Filter out all social conversation, greetings, and chitchat.
3. Extract clinically relevant content into a SOAP note.
4. Suggest appropriate CDT procedure codes.
5. Re-attribute speaker labels based on conversational context.

## Speaker Attribution Rules
- The DOCTOR leads, instructs, directs, uses clinical terminology, gives diagnoses
- The PATIENT responds, reports symptoms, asks personal questions, acknowledges
- Maintain speaker continuity across pauses (same speaker unless clear turn-taking)

## SOAP Note Structure
- Subjective: Chief complaint, patient-reported symptoms, pain, onset/duration
- Objective: Clinical findings (tooth numbers, surfaces, conditions), radiographic findings
- Assessment: Diagnosis with tooth numbers, classification (e.g., "Class II caries #14-MO")
- Plan: Procedures planned with CDT codes, materials, follow-up, patient instructions

## CDT Code Reference (use ONLY these codes)
D0120: Periodic oral evaluation
D0140: Limited problem-focused evaluation
D0150: Comprehensive oral evaluation
D0180: Comprehensive periodontal evaluation
D0210: Intraoral complete series (FMX)
D0220: Periapical radiograph
D0330: Panoramic radiograph
D1110: Adult prophylaxis (cleaning)
D1120: Child prophylaxis
D1206: Topical fluoride varnish
D1351: Sealant per tooth
D2140: Amalgam one surface primary/permanent
D2330: Resin composite one surface anterior
D2331: Resin composite two surfaces anterior
D2332: Resin composite three surfaces anterior
D2391: Resin composite one surface posterior
D2392: Resin composite two surfaces posterior
D2393: Resin composite three surfaces posterior
D2394: Resin composite four+ surfaces posterior
D2740: Crown porcelain/ceramic
D2750: Crown porcelain fused to high noble metal
D2950: Core buildup including pins
D3310: Root canal anterior
D3320: Root canal premolar
D3330: Root canal molar
D4341: Scaling and root planing per quadrant (4+ teeth)
D4342: Scaling and root planing per quadrant (1-3 teeth)
D4910: Periodontal maintenance
D5110: Complete denture maxillary
D5120: Complete denture mandibular
D6240: Pontic porcelain/ceramic
D6750: Crown porcelain fused to high noble metal (bridge)
D7140: Simple extraction erupted tooth
D7210: Surgical extraction erupted tooth
D7220: Removal impacted tooth soft tissue
D7240: Removal impacted tooth completely bony
D9110: Palliative treatment of dental pain
D9230: Nitrous oxide analgesia

## Rules
- Only use CDT codes from the reference list above
- Use tooth numbers in Universal numbering (1-32)
- If information is not mentioned in the transcript, do not fabricate it
- Keep each SOAP section concise but complete"""
```

### OllamaService with Health Check and Model Management
```python
# Source: ollama-python v0.6.1 docs + Ollama REST API docs
import logging
from ollama import Client, ResponseError

logger = logging.getLogger(__name__)

class OllamaService:
    """Manages Ollama client lifecycle and model interactions."""

    def __init__(self, host: str, model: str) -> None:
        self._client = Client(host=host)
        self._model = model

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def is_model_ready(self) -> bool:
        """Check if the configured model is pulled and available."""
        try:
            self._client.show(self._model)
            return True
        except ResponseError:
            return False

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        schema: dict,
        temperature: float = 0.0,
        num_ctx: int = 8192,
    ) -> str:
        """Generate structured output conforming to a JSON schema.

        Returns raw JSON string for caller to validate with Pydantic.
        """
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/nothink\n\n{user_content}"},
            ],
            format=schema,
            options={"temperature": temperature, "num_ctx": num_ctx},
        )
        return response.message.content

    def unload(self) -> None:
        """Unload model from GPU memory (keep_alive=0)."""
        try:
            self._client.chat(
                model=self._model, messages=[], keep_alive=0
            )
            logger.info("Ollama model %s unloaded", self._model)
        except Exception as e:
            logger.warning("Failed to unload model: %s", e)
```

### Config Extension for Ollama Settings
```python
# Source: Existing config.py pattern extended with Ollama settings
class Settings(BaseSettings):
    # ... existing settings ...

    # Ollama LLM
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_fallback_model: str = "qwen3:4b"
    ollama_temperature: float = 0.0
    ollama_num_ctx: int = 8192
```

### Testing: Fake OllamaService for Unit Tests
```python
# Source: Project testing patterns (conftest.py precedent)
import json

class FakeOllamaService:
    """Fake for unit tests -- validates prompt structure, returns canned response."""

    def __init__(self, response_data: dict | None = None):
        self._response_data = response_data or {
            "soap_note": {
                "subjective": "Patient reports sensitivity on upper right.",
                "objective": "Class II caries #14-MO, no periapical pathology.",
                "assessment": "Caries #14 MO, Class II.",
                "plan": "Composite restoration #14 MO.",
            },
            "cdt_codes": [{"code": "D2392", "description": "Composite 2 surfaces posterior"}],
            "speaker_chunks": [],
            "clinical_summary": "Routine restorative visit.",
        }
        self.last_system_prompt: str | None = None
        self.last_user_content: str | None = None
        self.call_count = 0

    def is_available(self) -> bool:
        return True

    def is_model_ready(self) -> bool:
        return True

    def generate_structured(
        self, system_prompt: str, user_content: str, schema: dict, **kwargs
    ) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_content = user_content
        self.call_count += 1
        return json.dumps(self._response_data)

    def unload(self) -> None:
        pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parse LLM text output with regex | Structured output via JSON schema (Ollama format param) | Dec 2024 (Ollama v0.5) | Eliminates JSON parsing failures; constrained decoding guarantees valid schema |
| Generic "output as JSON" instruction | Pydantic model_json_schema() -> format parameter | Dec 2024 | Type-safe, validated, IDE-friendly output handling |
| Keep model loaded permanently | keep_alive=0 for explicit unload | Ollama v0.3+ | Critical for sequential GPU loading in VRAM-constrained environments |
| Single model size assumption | Configurable model with VRAM-aware fallback | Ongoing | Supports GTX 1050 (4GB) through RTX cards (12GB+) |

**Deprecated/outdated:**
- Using `format="json"` without a schema: Still works but the model decides field names, leading to inconsistent output
- Ollama v0.4 and earlier: Did not support JSON schema in format parameter
- Using LangChain/LlamaIndex for simple Ollama calls: Adds unnecessary dependency weight for direct API usage

## VRAM Budget Analysis

### GTX 1050 (4GB VRAM) -- Minimum Hardware
| Component | VRAM | Notes |
|-----------|------|-------|
| Whisper small int8 | ~1.5GB | During transcription only |
| Qwen3 4B Q4_K_M | ~2.5GB | During extraction only |
| KV cache (8K ctx) | ~0.2GB | Scales with context length |
| OS/CUDA overhead | ~0.5GB | CUDA runtime, display |
| **Total per phase** | **~2.7GB** | Sequential only; never both |

### GTX 1070 Ti (8GB VRAM) -- Common Hardware
| Component | VRAM | Notes |
|-----------|------|-------|
| Whisper small int8 | ~1.5GB | During transcription only |
| Qwen3 8B Q4_K_M | ~5.2GB | During extraction only |
| KV cache (16K ctx) | ~0.5GB | Can afford larger context |
| OS/CUDA overhead | ~0.5GB | CUDA runtime, display |
| **Total per phase** | **~6.2GB** | Sequential only; fits comfortably |

**Conclusion:** Sequential loading is mandatory on both hardware tiers. On 8GB, Whisper (~1.5GB) + Qwen3 8B (~5.2GB) = ~6.7GB which *could* coexist, but leaves no room for KV cache. Sequential is safer and simpler.

## Open Questions

1. **Qwen3 4B quality for clinical extraction**
   - What we know: Qwen3 4B reportedly rivals Qwen2.5-72B on some benchmarks. General reasoning quality should be sufficient.
   - What's unclear: Specific quality for dental SOAP note extraction with CDT codes. No dental-specific benchmarks exist.
   - Recommendation: Build with 8B as default, test with 4B during human verification. If 4B quality is insufficient on 4GB hardware, consider CPU-only 8B (slow but higher quality) as an alternative fallback.

2. **Thinking mode interaction with structured output**
   - What we know: Qwen3 has thinking/non-thinking modes. `/nothink` in user message should disable it. Structured output format parameter constrains output.
   - What's unclear: Whether structured output format fully suppresses `<think>` tags, or whether they leak into the JSON.
   - Recommendation: Test both modes. If thinking tags appear in structured output, force `/nothink` and add explicit instruction in system prompt.

3. **Single-pass vs two-pass extraction**
   - What we know: Speaker re-attribution and SOAP note extraction could be done in one LLM call or two separate calls.
   - What's unclear: Whether a single call produces better results (more context) or worse (too many instructions).
   - Recommendation: Start with single-pass (one call produces both re-attributed speakers and SOAP note). If quality is poor, split into two passes: (1) speaker re-attribution, (2) SOAP extraction from re-attributed transcript.

4. **Ollama Windows installation and service management**
   - What we know: The server runs on Windows. Ollama must also run on Windows as a service.
   - What's unclear: Whether the user has Ollama installed already. Windows installation path and startup.
   - Recommendation: Document Ollama setup requirements. Provide clear error messages if Ollama is not reachable. Do not auto-install.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x --tb=short` |
| Full suite command | `pytest tests/ --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | LLM filters clinical from social content | unit + integration | `pytest tests/test_extractor.py -x` | No -- Wave 0 |
| CLI-02 | Output is structured SOAP note | unit + integration | `pytest tests/test_extractor.py::test_soap_structure -x` | No -- Wave 0 |
| CLI-03 | CDT codes suggested from Assessment/Plan | unit + integration | `pytest tests/test_extractor.py::test_cdt_codes -x` | No -- Wave 0 |
| CLI-04 | Speaker labels re-attributed by LLM | unit + integration | `pytest tests/test_speaker_reattribution.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --tb=short`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green + human verification of SOAP note quality

### Wave 0 Gaps
- [ ] `tests/test_ollama_service.py` -- covers OllamaService health check, model check, unload, generate_structured
- [ ] `tests/test_extractor.py` -- covers CLI-01, CLI-02, CLI-03 (transcript -> SOAP note pipeline)
- [ ] `tests/test_speaker_reattribution.py` -- covers CLI-04 (speaker label correction)
- [ ] `tests/test_clinical_models.py` -- covers Pydantic model validation (SoapNote, CdtCode, ExtractionResult)
- [ ] `tests/test_clinical_integration.py` -- integration test requiring real Ollama instance (marked with `@pytest.mark.integration`)
- [ ] Update `tests/conftest.py` -- add FakeOllamaService, sample transcript fixtures
- [ ] Framework install: `pip install ollama>=0.6.1` (add to pyproject.toml)

### Integration Test Strategy
Per CONTEXT.md locked decision: "No mocking away the LLM -- use real Ollama in integration tests (or a realistic fake that validates prompt/response structure)."

**Two-tier approach:**
1. **Unit tests (fast, no Ollama required):** Use `FakeOllamaService` that returns canned JSON matching the Pydantic schema. These validate the pipeline logic, error handling, and data transformations. Run in CI.
2. **Integration tests (slow, requires Ollama):** Use real Ollama with `qwen3:4b` (smaller, faster). These validate prompt quality, structured output compliance, and clinical extraction accuracy. Marked with `@pytest.mark.integration` and skipped in CI. Run locally before human verification.

```python
# conftest.py addition
import pytest

def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Run integration tests")

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="Need --integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
```

## Sources

### Primary (HIGH confidence)
- [ollama/ollama-python GitHub](https://github.com/ollama/ollama-python) -- Python client API, version 0.6.1, sync/async usage, error handling
- [Ollama Structured Outputs docs](https://docs.ollama.com/capabilities/structured-outputs) -- format parameter, JSON schema, Pydantic integration
- [Ollama API introduction](https://docs.ollama.com/api/introduction) -- REST API endpoints, base URL
- [Ollama FAQ](https://docs.ollama.com/faq) -- keep_alive parameter, model unloading, OLLAMA_KEEP_ALIVE
- [ollama PyPI](https://pypi.org/project/ollama/) -- version 0.6.1, MIT license, httpx dependency
- [Ollama model tags: qwen3](https://ollama.com/library/qwen3/tags) -- Model sizes: 8B=5.2GB Q4_K_M, 4B=2.5GB Q4_K_M

### Secondary (MEDIUM confidence)
- [Qwen3-8B Specifications](https://apxml.com/models/qwen3-8b) -- 8.19B params, 131K context, April 2025 release, Apache 2.0
- [Ollama VRAM Requirements Guide](https://localllm.in/blog/ollama-vram-requirements-for-local-llms) -- Q4_K_M 8B needs 6-7GB VRAM, KV cache scaling
- [DeepWiki: ollama-python Structured Outputs](https://deepwiki.com/ollama/ollama-python/4.4-structured-outputs) -- Pydantic pattern, temperature=0, validation
- [CDT Codes for 2025](https://qiaben.com/comprehensive-list-of-dental-procedure-codes-for-2025/) -- Code categories and descriptions
- [Ollama Thinking docs](https://docs.ollama.com/capabilities/thinking) -- /nothink, --think=false, thinking mode control

### Tertiary (LOW confidence)
- [Qwen3 4B quality claim](https://unsloth.ai/docs/models/qwen3-how-to-run-and-fine-tune) -- "Qwen3 4B rivals Qwen2.5-72B" -- needs validation with dental-specific testing
- [Partial GPU offload performance](https://collabnix.com/ollama-performance-tuning-gpu-optimization-techniques-for-production/) -- 4.7x slowdown with partial offload -- single source, plausible but unverified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Ollama Python client is well-documented, Pydantic structured outputs verified across multiple sources
- Architecture: MEDIUM-HIGH -- Sequential GPU loading pattern well-established; single-pass vs two-pass extraction needs empirical validation
- Pitfalls: HIGH -- VRAM constraints and context window limits verified across multiple sources; CDT hallucination is a known LLM limitation
- VRAM budget: MEDIUM -- Numbers from multiple sources but not verified on actual hardware; KV cache estimates are approximate

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (30 days -- Ollama and Qwen3 ecosystems are relatively stable)
