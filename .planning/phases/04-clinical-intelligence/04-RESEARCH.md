# Phase 4: Clinical Intelligence - Research

**Researched:** 2026-03-28
**Domain:** NLP pipeline enhancement -- Whisper vocabulary, LLM template composition, 3-way speaker classification, patient summary generation
**Confidence:** HIGH

## Summary

Phase 4 enhances four components of the existing v1 clinical pipeline, all of which are already working and covered by 249 passing tests. The changes are entirely additive -- expanding vocabulary constants, adding new keyword patterns, composing prompt overlays atop the existing extraction prompt, adding a second LLM call in the GPU handoff window, and adding a tab + print view to the review page. No new GPU-consuming models are introduced. No architectural changes to the pipeline.

The codebase is well-structured for these changes. The `DENTAL_INITIAL_PROMPT` string (whisper_service.py:24-53) is a single constant that needs expansion. The `classify_speaker()` function (session/speaker.py) uses regex pattern lists that need a third category. The `EXTRACTION_SYSTEM_PROMPT` (clinical/prompts.py) needs template composition. The `extract_with_gpu_handoff()` method (clinical/extractor.py:66-82) has a clear insertion point for the patient summary call. The review page (review.html) right panel needs tab navigation.

**Primary recommendation:** Implement in four independent work streams (vocabulary, templates, 3-way speaker, patient summary) that converge at the session stop / extraction flow. The vocabulary and templates share a touchpoint (hotwords passed per template), so those should be coordinated. Speaker and patient summary are fully independent.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Global expansion of `DENTAL_INITIAL_PROMPT` covering 4 term categories: anesthetics/meds, materials/brands, pathology/findings, anatomy/surfaces
- Use faster-whisper `hotwords` parameter for procedure-specific term boosting per appointment template
- Vocabulary is baked-in (one comprehensive set), not per-office configurable
- Learn-as-you-go: manual vocab file (plain text, loaded at startup, merged with base prompt) for v2. Auto-detection deferred to v3
- Must respect ~224 token limit for initial_prompt
- Dropdown + auto-detect hybrid for template selection before recording, default "General"
- If no template selected, LLM auto-detects appointment type from transcript during extraction
- 5 templates: comprehensive exam, restorative, hygiene/recall, endodontic, oral surgery
- Same SOAP structure (S/O/A/P) for all templates -- LLM emphasizes different details per template
- Template changeable at review time -- re-extraction with new template prompt
- Template selection flows into: (a) Whisper hotwords during recording, (b) extraction system prompt, (c) review page display
- Extend text-based keyword classifier to 3 roles: Doctor, Patient, Assistant
- Assistant keyword patterns across 4 categories: instrument/supply calls, patient comfort, procedural assists, charting/admin
- If classifier uncertain, default to doctor speech
- No audio-based diarization -- text-based + LLM only, zero VRAM cost
- LLM SpeakerReattributor enhanced with 3-role prompt
- Patient summary: plain-language (~6th-grade reading level), no CDT codes, no clinical jargon
- Content: what was done today, what comes next, home care instructions
- Generated as second LLM call during GPU handoff window (after SOAP, before Whisper reload)
- UI: tab in review page right panel, toggle "Clinical Note" / "Patient Summary"
- Patient summary editable before printing
- Print-ready HTML page via browser print dialog
- Separate prompt from SOAP extraction

### Claude's Discretion
- Exact keyword patterns for assistant classification (informed by the 4 categories)
- How to structure template-specific prompt overlays (Jinja2 composition, string concatenation, etc.)
- hotwords parameter format and which terms get hotwords vs initial_prompt
- Patient summary prompt engineering (reading level, tone, structure)
- Print page HTML layout and styling
- How the manual vocab file is loaded and merged at startup
- Error handling when template auto-detection confidence is low

### Deferred Ideas (OUT OF SCOPE)
- Auto-detection of vocab corrections from review screen edits -- v3
- Audio-based speaker embeddings via resemblyzer
- Per-office configurable vocabulary
- Hygienist as 4th speaker role (treated same as assistant)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-05 | Whisper vocabulary expanded with procedures, materials, surfaces, pathology, anatomy, findings, diagnoses using initial_prompt + hotwords | Expanded DENTAL_INITIAL_PROMPT constant, hotwords parameter on transcribe(), manual vocab file loading, template-specific hotwords mapping |
| CLI-06 | 5 appointment-type templates with template-specific extraction prompts and note structures | Template enum/model, prompt overlay composition in prompts.py, template dropdown UI, auto-detection fallback, re-extraction on template change |
| CLI-07 | 3-way speaker classification (Doctor/Patient/Assistant) via extended keyword classifier + LLM re-attribution | Extended _ASSISTANT_PATTERNS in session/speaker.py, updated SPEAKER_SYSTEM_PROMPT for 3 roles, SpeakerChunk model update |
| REV-04 | Plain-language patient summary at 6th-grade reading level alongside clinical SOAP note | PatientSummary Pydantic model, summary prompt, second LLM call in GPU handoff, review tab UI, print CSS |
</phase_requirements>

## Standard Stack

### Core (already installed, no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | >=1.0.3 | Transcription with initial_prompt + hotwords | Already in use; hotwords parameter available in transcribe() |
| ollama (Python) | >=0.6.1 | LLM inference via generate_structured() | Already in use; same client for SOAP + patient summary |
| FastAPI | >=0.135.0 | Web routes for template dropdown, summary tab, print view | Already in use |
| Jinja2 | >=3.1.0 | HTML templates for review tabs, print page | Already in use for all UI templates |
| Pydantic | (via pydantic-settings) | Models for templates, patient summary, speaker chunks | Already in use for all structured data |

### Supporting (no additions needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | >=2.0.0 | SSE for streaming transcript with 3-way speaker labels | Already in use |
| HTMX | 2.0.4 (CDN) | Tab switching, template dropdown, re-extraction trigger | Already in use |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| String concatenation for prompt composition | Jinja2 template rendering | Jinja2 adds complexity; string concat with f-strings is simpler for 5 templates and matches existing pattern |
| textstat library for reading level check | Manual prompt engineering for 6th-grade level | textstat would add a dependency for a quality check that the LLM prompt handles directly |

**Installation:** No new packages needed. Phase 4 uses only existing dependencies.

## Architecture Patterns

### Recommended Changes to Existing Structure
```
src/dental_notes/
├── clinical/
│   ├── models.py          # ADD: PatientSummary, AppointmentType enum
│   ├── prompts.py         # ADD: template overlays dict, patient summary prompt, compose_extraction_prompt()
│   ├── speaker.py         # UPDATE: SPEAKER_SYSTEM_PROMPT for 3 roles
│   ├── extractor.py       # UPDATE: extract_with_gpu_handoff() adds patient summary call
│   └── formatter.py       # UPDATE: format patient summary for clipboard
├── session/
│   ├── speaker.py         # ADD: _ASSISTANT_PATTERNS, update classify_speaker()
│   └── store.py           # ADD: appointment_type field to SavedSession, patient_summary field
├── transcription/
│   ├── whisper_service.py # UPDATE: expand DENTAL_INITIAL_PROMPT, add hotwords param, load vocab file
│   └── vocab.py           # NEW: load_custom_vocab(), merge with base prompt, TEMPLATE_HOTWORDS dict
├── templates/
│   ├── index.html         # UPDATE: add template dropdown before Record button
│   ├── review.html        # UPDATE: tab navigation (Clinical Note / Patient Summary / Print)
│   ├── _review_note.html  # UPDATE: wrap in tab content div
│   ├── _review_summary.html  # NEW: patient summary tab content (editable textarea)
│   └── _print_summary.html   # NEW: print-optimized patient summary page
├── static/
│   ├── style.css          # UPDATE: tab styles, print CSS (@media print)
│   └── review.js          # UPDATE: tab switching logic, print button handler
└── ui/
    └── routes.py          # ADD: routes for template selection, summary generation, print view
```

### Pattern 1: Template Prompt Composition
**What:** Base extraction prompt + template-specific overlay concatenated at extraction time
**When to use:** Every extraction call
**Example:**
```python
# In clinical/prompts.py

TEMPLATE_OVERLAYS: dict[str, str] = {
    "comprehensive_exam": (
        "## Template: Comprehensive Exam\n"
        "Emphasize: full-mouth findings, perio assessment, radiographic review, "
        "treatment planning discussion, all teeth examined.\n"
        "Objective should include: complete charting, existing restorations, "
        "periodontal screening, oral cancer screening findings.\n"
    ),
    "restorative": (
        "## Template: Restorative Procedure\n"
        "Emphasize: anesthetic type/amount/site, material and shade selection, "
        "step-by-step procedure narrative, post-op instructions.\n"
        "Objective should include detailed procedure documentation.\n"
    ),
    # ... hygiene_recall, endodontic, oral_surgery
}

def compose_extraction_prompt(template_type: str | None = None) -> str:
    """Compose full extraction prompt from base + template overlay."""
    base = EXTRACTION_SYSTEM_PROMPT
    if template_type and template_type in TEMPLATE_OVERLAYS:
        return base + "\n\n" + TEMPLATE_OVERLAYS[template_type]
    return base
```

### Pattern 2: Hotwords per Template
**What:** Template-specific hotword strings passed to WhisperService.transcribe()
**When to use:** During recording, when a template is selected
**Example:**
```python
# In transcription/vocab.py

TEMPLATE_HOTWORDS: dict[str, str] = {
    "comprehensive_exam": "periodontal screening oral cancer FMX bitewings probing depths",
    "restorative": "Lidocaine Septocaine composite shade bonding light cure matrix band",
    "hygiene_recall": "prophylaxis scaling calculus BOP probing fluoride home care",
    "endodontic": "pulpotomy root canal working length gutta-percha obturation apex",
    "oral_surgery": "extraction forceps elevator bone graft sutures socket preservation",
}
```

### Pattern 3: Second LLM Call in GPU Handoff
**What:** Patient summary generated between SOAP extraction and Ollama unload
**When to use:** Every extraction that produces a SOAP note
**Example:**
```python
# In clinical/extractor.py -- updated extract_with_gpu_handoff()

def extract_with_gpu_handoff(
    self, transcript: str, whisper_service, template_type: str | None = None
) -> ExtractionResult:
    whisper_service.unload()
    try:
        result = self.extract(transcript, template_type)
        # Second LLM call: patient summary (still in GPU handoff window)
        summary = self._generate_patient_summary(result.soap_note)
        result.patient_summary = summary
    finally:
        self._ollama.unload()
        whisper_service.load_model()
    return result
```

### Pattern 4: Manual Vocab File Loading
**What:** Plain text file loaded at startup, merged with base initial_prompt
**When to use:** At WhisperService initialization and on config reload
**Example:**
```python
# In transcription/vocab.py

from pathlib import Path

CUSTOM_VOCAB_PATH = Path("vocab.txt")  # Configurable via Settings

def load_custom_vocab(path: Path = CUSTOM_VOCAB_PATH) -> str:
    """Load custom vocabulary terms from a plain text file.

    File format: one term or phrase per line. Lines starting with # are comments.
    Returns space-separated string of terms for appending to initial_prompt.
    """
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    terms = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    return " ".join(terms)
```

### Anti-Patterns to Avoid
- **Separate SOAP sections per template:** All templates use the same S/O/A/P structure. Do NOT create different Pydantic models per template -- the emphasis difference lives in the prompt only.
- **Audio-based diarization:** Do NOT import pyannote, resemblyzer, or any audio embedding library. The 3-way classification is text-only.
- **Blocking LLM calls in async routes:** Always run extraction via `loop.run_in_executor()` as the existing code does.
- **Exceeding 224-token initial_prompt limit:** The expanded prompt MUST be tested for token count. If it exceeds ~224 tokens, use the hotwords parameter for overflow terms instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading level assessment | Custom Flesch-Kincaid calculator | LLM prompt instruction "write at 6th-grade reading level" | Research shows LLMs reliably produce ~6th grade text when prompted; textstat would add unnecessary dependency |
| JSON schema for Ollama | Manual schema dict construction | Pydantic `.model_json_schema()` + existing `_dereference_schema()` | Already proven pattern in OllamaService |
| Tab UI component | Custom JS tab framework | Simple HTMX + CSS class toggling | Matches existing HTMX-first UI pattern; no new JS framework needed |
| Print layout | PDF generation library (ReportLab, etc.) | `@media print` CSS + `window.print()` | Browser print dialog handles PDF export natively; patient summary is simple text |
| Token counting for initial_prompt | Build tokenizer integration | Heuristic: ~4 chars per token (OpenAI guidance) + manual testing | CTranslate2's tokenizer would add complexity; the ~224 token limit is approximate anyway |

**Key insight:** Phase 4 is prompt engineering and text classification -- not infrastructure. Every capability is achieved by composing text (prompts, keyword lists, vocabulary strings) and routing it through existing pipeline components.

## Common Pitfalls

### Pitfall 1: Exceeding initial_prompt Token Limit
**What goes wrong:** Expanded vocabulary prompt exceeds ~224 tokens, causing Whisper to silently truncate from the beginning, losing the most important terms.
**Why it happens:** The existing prompt is already ~200 tokens. Adding materials, pathology, anatomy terms pushes past the limit.
**How to avoid:** (1) Count tokens with heuristic (text length / 4). (2) Move the LEAST important terms to hotwords parameter. (3) Keep the most-misrecognized terms in initial_prompt. (4) Template-specific hotwords carry the procedure-specific boost.
**Warning signs:** Dental terms that were previously transcribed correctly start being misrecognized after vocabulary expansion.

### Pitfall 2: Template Prompt Bloat Degrading LLM Output
**What goes wrong:** Template overlay makes the total system prompt too long, causing the LLM to lose focus on the critical extraction rules.
**Why it happens:** Adding 5 template overlays with detailed instructions on top of the already-long EXTRACTION_SYSTEM_PROMPT (~193 lines).
**How to avoid:** Keep template overlays SHORT (3-5 lines of emphasis guidance). The base prompt already covers SOAP structure thoroughly. Template overlays only adjust what to emphasize, not restate how to write SOAP.
**Warning signs:** Extraction quality drops for non-template-specific content (e.g., CDT codes become less accurate when using a restorative template).

### Pitfall 3: Assistant Keywords Stealing Doctor Classifications
**What goes wrong:** Adding assistant patterns that overlap with doctor speech causes doctor statements to be misclassified as assistant.
**Why it happens:** Terms like "suction," "bite down," and "rinse" appear in both doctor instructions and assistant actions.
**How to avoid:** (1) Assistant patterns should emphasize CONTEXT not just keywords -- e.g., "suction here" vs "I need suction" (assistant) vs "let me suction this area" (doctor). (2) When classifier is uncertain, DEFAULT TO DOCTOR (locked decision). (3) Score threshold: assistant score must exceed doctor score AND a minimum threshold.
**Warning signs:** Doctor instruction text in the transcript starts appearing as "Assistant:" labels.

### Pitfall 4: Patient Summary Echoing Clinical Jargon
**What goes wrong:** The patient summary contains clinical terminology (CDT codes, Latin terms, abbreviations) despite the plain-language prompt.
**Why it happens:** The LLM sees the clinical SOAP note content and bleeds jargon into the summary.
**How to avoid:** (1) Use the TRANSCRIPT as input to the patient summary prompt, NOT the SOAP note. (2) Explicitly list forbidden terms: "Do NOT use: CDT codes, Latin terms, medical abbreviations." (3) Include positive examples: "Instead of 'Class II caries on #14 MO', write 'a cavity between your upper teeth on the right side'."
**Warning signs:** Patient summary contains terms like "periapical," "D2392," or "MOD."

### Pitfall 5: GPU Handoff Timeout on Two LLM Calls
**What goes wrong:** Adding the patient summary as a second LLM call doubles the time the GPU is occupied, and the user perceives a long wait after stopping recording.
**Why it happens:** Each LLM call to Qwen3 8B takes 10-30 seconds. Two calls = 20-60 seconds.
**How to avoid:** (1) Patient summary can use a shorter context window (fewer tokens needed for simple text). (2) Set lower num_ctx for summary generation (e.g., 4096 vs 8192). (3) Consider making summary generation async (generate after page load, show spinner). (4) The summary prompt is simpler, so generation should be faster than SOAP extraction.
**Warning signs:** Session stop takes noticeably longer than v1 (>45 seconds).

### Pitfall 6: Tab State Lost on HTMX Swap
**What goes wrong:** When the user is on the Patient Summary tab and triggers re-extraction (Regenerate button), the HTMX swap replaces the note panel content and resets to the Clinical Note tab.
**Why it happens:** HTMX swaps innerHTML of #note-panel, which destroys the tab state.
**How to avoid:** (1) Store active tab in a data attribute or hidden input. (2) After HTMX swap, restore the active tab via htmx:afterSwap event listener. (3) Alternatively, use hx-swap-oob to update tab contents independently.
**Warning signs:** User clicks Regenerate while viewing Patient Summary and gets dumped back to Clinical Note tab.

## Code Examples

### Expanded DENTAL_INITIAL_PROMPT (CLI-05)
```python
# Source: existing whisper_service.py pattern + CONTEXT.md locked decisions
# Must stay under ~224 tokens. Prioritize most-misrecognized terms.

DENTAL_INITIAL_PROMPT = (
    "Dental clinical appointment transcription. "
    # Tooth numbering (keep -- works well in v1)
    "Universal tooth numbering: teeth 1 through 32. "
    # Surfaces (keep)
    "Mesial, occlusal, distal, buccal, lingual, facial, incisal. "
    "MOD, DO, BL, MO, OL, MODBL. "
    # Anesthetics and medications (NEW)
    "Lidocaine, Septocaine, Marcaine, articaine. "
    "Epinephrine 1:100,000 and 1:200,000. Inferior alveolar nerve block. "
    # Materials and brands (EXPANDED)
    "Herculite, Estelite, Paracore, Luxatemp, Fuji, IRM, Dycal. "
    "E.max, zirconia, PFM, lithium disilicate, composite, amalgam. "
    # Pathology and findings (NEW)
    "Radiolucency, periapical, dehiscence, fenestration. "
    "Caries classification, reversible pulpitis, irreversible pulpitis. "
    # Anatomy (NEW)
    "CEJ, furcation, mandibular canal, mental foramen. "
    "Lingual, buccal, mesial, distal, palatal. "
    # Procedures (keep condensed)
    "SRP, scaling and root planing, prophylaxis, root canal, extraction. "
    "Crown, bridge, veneer, onlay, inlay, implant, denture. "
    # CDT codes (keep abbreviated)
    "CDT code D0120, D0150, D2391, D2740, D3330, D4341. "
)
```

### Template Enum and Hotwords Mapping (CLI-06)
```python
# In clinical/models.py

from enum import Enum

class AppointmentType(str, Enum):
    """Appointment type for template-specific extraction."""
    GENERAL = "general"
    COMPREHENSIVE_EXAM = "comprehensive_exam"
    RESTORATIVE = "restorative"
    HYGIENE_RECALL = "hygiene_recall"
    ENDODONTIC = "endodontic"
    ORAL_SURGERY = "oral_surgery"
```

### 3-Way Speaker Classification (CLI-07)
```python
# In session/speaker.py -- new assistant patterns

_ASSISTANT_PATTERNS = [
    # Instrument and supply calls
    r"\b(?:suction|two.?by.?two|explorer|cotton roll|bite block|"
    r"matrix band|wedge|retractor|high.?speed|slow.?speed|handpiece)\b",
    # Patient comfort phrases
    r"\b(?:you'?re doing (?:great|well|good)|almost done|"
    r"rinse and spit|are you (?:okay|alright|comfortable)|"
    r"just a little (?:more|longer)|doing (?:great|well))\b",
    # Procedural assists
    r"\b(?:isolation complete|impression set|light cure|mixing|"
    r"ready (?:for|to)|loaded|placed|seated|cement mixed)\b",
    # Charting and admin
    r"\b(?:noted|got it|which tooth|what shade|"
    r"want me to|should I|do you need)\b",
]

def classify_speaker(text: str, prev_speaker: str | None = None) -> str:
    """Classify text as 'Doctor', 'Patient', or 'Assistant'."""
    doctor_score = sum(len(r.findall(text)) for r in _doctor_re)
    patient_score = sum(len(r.findall(text)) for r in _patient_re)
    assistant_score = sum(len(r.findall(text)) for r in _assistant_re)

    scores = {"Doctor": doctor_score, "Patient": patient_score, "Assistant": assistant_score}
    max_label = max(scores, key=scores.get)
    max_score = scores[max_label]

    # If all scores are 0 (ambiguous), alternate or default to Doctor
    if max_score == 0:
        if prev_speaker == "Doctor":
            return "Patient"
        if prev_speaker == "Patient":
            return "Doctor"
        return "Doctor"

    # If tie between assistant and doctor, default to Doctor (locked decision)
    if assistant_score == doctor_score and assistant_score >= patient_score:
        return "Doctor"

    return max_label
```

### Patient Summary Prompt (REV-04)
```python
# In clinical/prompts.py

PATIENT_SUMMARY_PROMPT = """You are writing a patient handout for a dental visit. \
Write in plain, friendly language that a 6th-grader could understand. \
No medical abbreviations. No CDT codes. No Latin terms.

## What to Include
1. **What we did today** -- describe the procedure or exam in everyday words
2. **What comes next** -- upcoming appointments, follow-up needed
3. **Home care instructions** -- post-procedure care, medications, diet restrictions

## Writing Rules
- Use "you/your" (speak directly to the patient)
- Use short sentences (under 20 words each)
- Replace clinical terms with plain alternatives:
  - "composite restoration" -> "tooth-colored filling"
  - "periapical radiolucency" -> "infection at the root tip"
  - "scaling and root planing" -> "deep cleaning"
  - "Class II caries" -> "cavity between the teeth"
  - "extraction" -> "tooth removal"
  - "crown" -> "cap for your tooth"
- If medications were prescribed, include: name, how much, how often, for how long
- If no medications, skip that section entirely
- Keep total length under 250 words
- Do NOT include insurance information, costs, or CDT codes

## Input
You will receive a transcript of the dental appointment. \
Extract the relevant information and write the patient summary."""
```

### Print-Ready CSS
```css
/* In static/style.css -- @media print rules for patient summary */

@media print {
    /* Hide everything except the print content */
    header, footer, .controls-section, .mic-section,
    .transcript-panel, .review-actions, .panel-header-actions,
    .tab-buttons, .sessions-section, .regen-banner { display: none !important; }

    .summary-print-content {
        display: block !important;
        font-family: "Georgia", serif;
        font-size: 12pt;
        line-height: 1.6;
        max-width: 100%;
        margin: 0;
        padding: 0.5in;
    }

    .summary-print-content h1 { font-size: 16pt; margin-bottom: 0.5em; }
    .summary-print-content h2 { font-size: 13pt; margin-top: 1em; }
    .summary-print-content p { margin-bottom: 0.5em; }

    @page { margin: 0.75in; }
}
```

### Tab Navigation HTML (review.html right panel)
```html
<!-- Tab buttons -->
<div class="tab-buttons">
    <button type="button" class="tab-btn active" data-tab="clinical-note">
        Clinical Note
    </button>
    <button type="button" class="tab-btn" data-tab="patient-summary">
        Patient Summary
    </button>
</div>

<!-- Tab content: Clinical Note -->
<div class="tab-content active" id="tab-clinical-note">
    {% include "_review_note.html" %}
</div>

<!-- Tab content: Patient Summary -->
<div class="tab-content" id="tab-patient-summary">
    {% include "_review_summary.html" %}
</div>
```

## State of the Art

| Old Approach (v1) | Current Approach (Phase 4) | Impact |
|---|---|---|
| Single DENTAL_INITIAL_PROMPT for all appointments | Base prompt + template-specific hotwords | Better term recognition per procedure type |
| 2-way speaker classification (Doctor/Patient) | 3-way (Doctor/Patient/Assistant) with keyword + LLM | More accurate notes for procedures with dental assistants |
| Monolithic extraction prompt | Base prompt + template overlay composition | Template-specific emphasis without duplicating the full prompt |
| SOAP note only | SOAP note + patient summary in same GPU handoff | Patient gets a take-home handout alongside clinical note |
| Static review page with single panel | Tabbed right panel (Clinical / Summary / Print) | More organized review workflow |

**Deprecated/outdated:**
- The existing `DENTAL_INITIAL_PROMPT` at ~200 tokens will be replaced with a reorganized version that prioritizes most-misrecognized terms
- The 2-way `classify_speaker()` function will be extended (not replaced) to handle 3 roles

## Open Questions

1. **Exact token count of expanded initial_prompt**
   - What we know: Current prompt is ~200 tokens. 224 is the hard limit. We need to add anesthetics, materials, pathology, anatomy terms.
   - What's unclear: Exactly which terms fit within the remaining ~24 tokens before needing to overflow to hotwords.
   - Recommendation: Write the expanded prompt, estimate at ~4 chars/token, and measure. Move lowest-priority terms to hotwords if over limit. This is an implementation detail resolved during coding.

2. **Patient summary generation time**
   - What we know: Single LLM call takes 10-30s. Summary is simpler than SOAP so should be faster.
   - What's unclear: Exact latency impact of adding a second LLM call in the GPU handoff window.
   - Recommendation: Implement with lower num_ctx (4096) for the summary call. If too slow, make it async (generate after review page loads, show spinner). Test with real hardware.

3. **Assistant pattern overlap with doctor patterns**
   - What we know: Terms like "suction," "bite down," "rinse" overlap. CONTEXT.md says moderate overlap is expected and best-effort is acceptable.
   - What's unclear: How many false positives in practice with the proposed keyword patterns.
   - Recommendation: Start conservative (strict patterns, high threshold), tune based on test transcripts. Default-to-doctor fallback is the safety net.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ with pytest-asyncio 0.23+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q --tb=short` |
| Full suite command | `pytest tests/ -q --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-05 | Expanded initial_prompt is valid string under token limit | unit | `pytest tests/test_whisper_service.py -x` | Exists (update needed) |
| CLI-05 | hotwords parameter accepted by transcribe() | unit | `pytest tests/test_whisper_service.py::test_transcribe_accepts_hotwords -x` | Wave 0 |
| CLI-05 | Custom vocab file loaded and merged | unit | `pytest tests/test_vocab.py -x` | Wave 0 |
| CLI-06 | Template overlay composes with base prompt | unit | `pytest tests/test_prompts.py -x` | Wave 0 |
| CLI-06 | AppointmentType enum has all 5 types + general | unit | `pytest tests/test_clinical_models.py -x` | Exists (update needed) |
| CLI-06 | Template selection stored in SavedSession | unit | `pytest tests/test_session_store.py -x` | Exists (update needed) |
| CLI-06 | Re-extraction with different template works | unit | `pytest tests/test_extractor.py -x` | Exists (update needed) |
| CLI-06 | Auto-detect fallback when no template selected | unit | `pytest tests/test_extractor.py::test_auto_detect_template -x` | Wave 0 |
| CLI-07 | classify_speaker returns Assistant for assistant text | unit | `pytest tests/test_speaker.py -x` | Exists (update needed) |
| CLI-07 | classify_speaker defaults to Doctor on tie | unit | `pytest tests/test_speaker.py::test_assistant_doctor_tie_defaults_doctor -x` | Wave 0 |
| CLI-07 | SpeakerReattributor handles 3 roles | unit | `pytest tests/test_speaker_reattribution.py -x` | Exists (update needed) |
| CLI-07 | SpeakerChunk accepts "Assistant" speaker | unit | `pytest tests/test_clinical_models.py -x` | Exists (update needed) |
| REV-04 | PatientSummary model validates correctly | unit | `pytest tests/test_clinical_models.py::TestPatientSummary -x` | Wave 0 |
| REV-04 | Patient summary generated in GPU handoff | unit | `pytest tests/test_extractor.py::test_gpu_handoff_generates_summary -x` | Wave 0 |
| REV-04 | Patient summary prompt contains plain-language rules | unit | `pytest tests/test_prompts.py::test_patient_summary_prompt -x` | Wave 0 |
| REV-04 | Review page renders both tabs | unit | `pytest tests/test_review_routes.py -x` | Exists (update needed) |
| REV-04 | Print CSS hides non-print elements | smoke | Manual: open print preview in browser | Manual only |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q --tb=short`
- **Per wave merge:** `pytest tests/ -q --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_vocab.py` -- covers CLI-05 (custom vocab loading, merge logic)
- [ ] `tests/test_prompts.py` -- covers CLI-06 (template composition, patient summary prompt constants)
- [ ] Update `tests/test_speaker.py` -- add assistant classification test cases for CLI-07
- [ ] Update `tests/test_speaker_reattribution.py` -- add 3-role reattribution tests for CLI-07
- [ ] Update `tests/test_clinical_models.py` -- add AppointmentType, PatientSummary model tests
- [ ] Update `tests/test_extractor.py` -- add template-aware extraction, patient summary generation tests
- [ ] Update `tests/test_whisper_service.py` -- add hotwords parameter acceptance test
- [ ] Update `tests/test_review_routes.py` -- add tab rendering and patient summary display tests
- [ ] Update `tests/test_session_store.py` -- add appointment_type field persistence tests
- [ ] Update `tests/conftest.py` -- add FakeOllamaService variant returning patient summary data

## Sources

### Primary (HIGH confidence)
- **Codebase analysis:** Direct reading of all 25 source files and 23 test files in dental-notes v2
- [faster-whisper transcribe.py](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py) -- hotwords parameter type is `Optional[str]`, space-separated string, has no effect when prefix is not None
- [OpenAI Whisper prompting guide](https://cookbook.openai.com/examples/whisper_prompting_guide) -- 224 token limit for initial_prompt, only affects first 30-second segment
- [Ollama structured outputs docs](https://docs.ollama.com/capabilities/structured-outputs) -- JSON schema format for structured generation

### Secondary (MEDIUM confidence)
- [OpenAI Whisper discussion #1386](https://github.com/openai/whisper/discussions/1386) -- initial_prompt token limit is 224 tokens, verified by multiple users
- [LLM patient readability study (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11795904/) -- LLMs produce ~6th grade reading level when prompted explicitly
- [MDN @media print guide](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing) -- CSS print media query patterns

### Tertiary (LOW confidence)
- None -- all findings verified through primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all changes extend existing code
- Architecture: HIGH -- all integration points verified by reading existing code (line numbers confirmed)
- Pitfalls: HIGH -- pitfalls derived from actual code constraints (224 token limit, GPU handoff timing, keyword overlap) and locked decisions
- Code examples: MEDIUM -- patterns match existing codebase conventions but specific implementation details will be refined during coding

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable -- no fast-moving external dependencies)
