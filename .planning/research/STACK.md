# Stack Research

**Domain:** Local-first ambient clinical note-taking (dental)
**Researched:** 2026-03-05
**Confidence:** MEDIUM-HIGH

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| faster-whisper | 1.1.0+ | Speech-to-text transcription | CTranslate2-based, 4x faster than OpenAI Whisper, INT8 quantization fits large-v3 in ~3GB VRAM. User already runs it successfully in whisper-ptt. Python-native. |
| Ollama | 0.9.x | Local LLM inference server | Auto-detects NVIDIA GPU, OpenAI-compatible API, structured JSON output, trivial Windows install, manages model downloads/quantization. |
| Qwen3 8B (Q4_K_M) | qwen3:8b | Clinical note structuring | 5.2GB download, fits 8GB VRAM at Q4_K_M, 32K native context, superior structured JSON output, Apache 2.0 license. Outperforms Llama 3.1 8B on structured data extraction tasks. |
| silero-vad | 6.2.1 | Voice activity detection | <1ms per chunk on CPU, 2MB model, MIT license, 4x fewer errors than WebRTC VAD. Already used in whisper-ptt. No GPU needed. |
| pyannote-audio | 4.0.4 | Speaker diarization | Best open-source diarization (DER ~11-19%), pure PyTorch, separates dentist from patient. Run post-hoc, not real-time. |
| Python | 3.12 | Application language | User's primary language, all ML libraries have first-class support, existing whisper-ptt codebase to build on. |
| sounddevice | 0.5.x | Audio capture | PortAudio bindings, cross-platform, callback-based streaming, 16kHz capture. Already used in whisper-ptt. |
| FastAPI | 0.115+ | Local HTTP API | Serves web UI, handles async transcription/LLM requests, OpenAPI docs auto-generated. User has extensive FastAPI experience (dental-notes, tax-shield). |

### Speech-to-Text: Model Selection Guide

| Model | Parameters | VRAM (INT8) | VRAM (FP16) | Speed (RTF) | Accuracy (WER) | Recommendation |
|-------|-----------|-------------|-------------|-------------|-----------------|----------------|
| tiny.en | 39M | ~0.5GB | ~0.5GB | ~32x RT | ~7.7% | Testing only |
| base.en | 74M | ~0.5GB | ~0.7GB | ~16x RT | ~5.8% | Live preview (fast feedback) |
| small.en | 244M | ~1GB | ~1.5GB | ~6x RT | ~4.3% | Good speed/accuracy balance |
| medium.en | 769M | ~2GB | ~3GB | ~2x RT | ~3.5% | Strong accuracy, still real-time |
| large-v3 | 1.55B | ~3.1GB | ~4.7GB | ~1x RT | ~2.5% | Best accuracy, fits 8GB |
| large-v3-turbo | 809M | ~2GB | ~3GB | ~6x RT | ~2.8% | Best speed/accuracy tradeoff |

**Primary recommendation: large-v3-turbo (INT8)** -- near large-v3 accuracy at 6x the speed, ~2GB VRAM, leaves room for Ollama LLM on same GPU.

**Confidence:** HIGH -- benchmarks from multiple sources, user already runs faster-whisper.

### Local LLM: Model Selection Guide

| Model | Size (Q4) | VRAM | Context | Structured JSON | Medical Knowledge | Recommendation |
|-------|-----------|------|---------|-----------------|-------------------|----------------|
| Qwen3 8B | 5.2GB | ~6GB | 32K | Excellent | Good | **Primary choice** |
| Llama 3.1 8B | 4.7GB | ~6GB | 128K | Good | Good | Fallback if Qwen3 struggles |
| Phi-4-mini (3.8B) | 2.4GB | ~3GB | 128K | Good | Moderate | If VRAM is tight (concurrent use) |
| Gemma 2 9B | 5.4GB | ~6GB | 8K | Good | Good | Alternative, short context |
| Mistral 7B v0.3 | 4.1GB | ~5GB | 32K | Good | Moderate | Lightweight alternative |

**Primary recommendation: Qwen3 8B (Q4_K_M)** -- best structured JSON output among 8B-class models, good medical text understanding, Apache 2.0 license.

**VRAM budget on GTX 1070 Ti (8GB):**
- faster-whisper large-v3-turbo INT8: ~2GB
- Qwen3 8B Q4_K_M: ~6GB
- Total concurrent: ~8GB (tight but feasible)
- Safer: Run sequentially -- transcribe first, then structure with LLM

**Confidence:** MEDIUM -- model benchmarks verified, but dental-specific SOAP note quality needs empirical testing. No dental-specific fine-tuned models exist.

### Audio Processing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| sounddevice | 0.5.x | Audio capture from microphone | PortAudio bindings, callback streaming, proven in whisper-ptt |
| noisereduce | 3.0+ | Spectral gating noise reduction | Stationary + non-stationary modes, PyTorch backend available, handles dental drill/suction noise |
| scipy.signal | (via scipy) | Audio preprocessing | Bandpass filtering, resampling, signal normalization |
| numpy | 1.26+ | Audio buffer management | Array operations for audio chunks, proven in whisper-ptt |

### Application Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI + uvicorn | 0.115+ / 0.30+ | Local HTTP backend | Async, WebSocket support for streaming, auto-generated OpenAPI. User's strongest framework. |
| HTML/CSS/JS (vanilla + htmx) | htmx 2.0 | Web UI served locally | No build step, instant reload, server-sent events for live transcription. Opens in any browser. |
| pystray | 0.19+ | System tray icon | Background service management, notifications, start/stop controls. Already used in whisper-ptt. |

**Why NOT Tauri/Electron:**
- Tauri would require Rust knowledge for the backend (unnecessary complexity)
- Electron adds 200-300MB RAM overhead that could go to ML models
- A locally-served web app gives identical UX with zero framework overhead
- User can access from phone on same network (like the existing dental-notes workflow)

**Confidence:** HIGH -- user has extensive FastAPI experience, and this architecture mirrors the working whisper-ptt + dental-notes patterns.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ollama (Python client) | 0.4+ | Python bindings for Ollama API | LLM inference calls from FastAPI backend |
| pydantic | 2.7+ | JSON schema validation | Validate LLM structured output, API request/response models |
| jinja2 | 3.1+ | Template rendering | HTML templates for web UI, note format templates |
| websockets | 13.0+ | WebSocket support | Real-time transcription streaming to browser |
| httpx | 0.27+ | Async HTTP client | Backend calls to Ollama API |
| python-multipart | 0.0.9+ | File upload support | Audio file upload endpoint |
| watchfiles | 0.22+ | File watching | Hot reload during development |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Lint + format | User's standard Python toolchain |
| mypy | Type checking | Strict mode per user conventions |
| pytest + pytest-cov | Testing | 80%+ coverage target per user standards |
| pytest-asyncio | Async test support | For FastAPI endpoint tests |

---

## Installation

```bash
# Create project
cd ~/claude
mkdir -p ambient-dental/
cd ambient-dental/

# Python environment
python3.12 -m venv .venv
source .venv/bin/activate

# Core ML dependencies (CUDA)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper>=1.1.0
pip install silero-vad>=6.0

# Local LLM (Ollama installed separately on Windows)
pip install ollama>=0.4.0

# Audio
pip install sounddevice>=0.5.0
pip install noisereduce>=3.0.0
pip install numpy>=1.26

# Web framework
pip install "fastapi[standard]>=0.115.0"
pip install uvicorn[standard]>=0.30.0
pip install jinja2>=3.1.0
pip install python-multipart>=0.0.9
pip install websockets>=13.0
pip install httpx>=0.27.0

# Speaker diarization (optional, Phase 2+)
pip install pyannote.audio>=4.0.0

# System tray
pip install pystray>=0.19.0
pip install Pillow>=10.0

# Dev dependencies
pip install -D ruff mypy pytest pytest-cov pytest-asyncio
```

```powershell
# Ollama (Windows installer -- run on Windows side, not WSL)
# Download from https://ollama.com/download/windows
# After install:
ollama pull qwen3:8b
ollama pull phi4-mini  # smaller fallback
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| faster-whisper | whisper.cpp | If you need C/C++ integration or Apple Silicon optimization. faster-whisper is better for Python ecosystem and has equivalent or better performance on NVIDIA GPUs. |
| faster-whisper | OpenAI Whisper (original) | Never for local use -- 4x slower, 2x more VRAM, same accuracy. |
| Ollama | llama-cpp-python | If you need tighter Python integration without a separate server process. Ollama is simpler to install/manage and auto-handles GPU offloading. |
| Ollama | vLLM | If you have 24GB+ VRAM and need production throughput. Overkill for single-user local inference. |
| Qwen3 8B | Llama 3.1 8B | If Qwen3 produces poor dental SOAP notes in testing. Llama 3.1 has 128K context (vs 32K) which helps for very long appointments. |
| Qwen3 8B | Phi-4-mini (3.8B) | If running transcription + LLM concurrently on 8GB GPU. Phi-4 uses ~3GB VRAM vs ~6GB. Accuracy tradeoff. |
| FastAPI + htmx | Tauri | If you want a native desktop feel with OS integration. Adds Rust complexity, npm toolchain, and heavier build process. |
| FastAPI + htmx | Electron | Never -- 200-300MB RAM overhead, Chromium bundled, no benefit over opening browser to localhost. |
| sounddevice | PyAudio | Never -- PyAudio has poor maintenance, difficult Windows builds, and sounddevice is strictly superior. |
| pyannote | NeMo diarization | If pyannote VRAM is too high. NeMo's Sortformer is newer but requires more careful resource management. |
| silero-vad | pyannote VAD | Never for real-time -- pyannote VAD doesn't support streaming and is slow on short segments. |
| silero-vad | WebRTC VAD | Never -- 4x higher error rate than Silero with worse accuracy in noisy environments. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| OpenAI Whisper (original Python) | 4x slower, 2x VRAM, same accuracy as faster-whisper | faster-whisper |
| PyAudio | Poorly maintained, difficult Windows builds, callback issues | sounddevice |
| WebRTC VAD | 50% TPR at 5% FPR vs Silero's 87.7% -- misses half of speech | silero-vad |
| Cloud APIs (OpenAI, Anthropic) | Violates local-first/HIPAA constraint, requires internet | Ollama + local models |
| Electron | 200-300MB RAM overhead, bundles Chromium unnecessarily | FastAPI + browser |
| whisper (pip install openai-whisper) | Pulls full PyTorch Whisper, slower, more VRAM | faster-whisper |
| Vosk | Older technology, lower accuracy than Whisper-based models | faster-whisper |
| SpeechRecognition (Python library) | Wrapper around cloud APIs or CMU Sphinx (outdated) | faster-whisper |
| Dragon NaturallySpeaking | Proprietary, expensive, no programmatic integration | faster-whisper + custom vocabulary |

---

## Stack Patterns by Variant

**If VRAM is tight (GTX 1050 4GB):**
- Use faster-whisper small.en (INT8, ~1GB VRAM)
- Use Phi-4-mini Q4 (~3GB VRAM) instead of Qwen3 8B
- Run sequentially, never concurrently
- Skip pyannote diarization (too VRAM-hungry)

**If VRAM is generous (RTX 3070+ 8-12GB):**
- Use faster-whisper large-v3-turbo (FP16, ~3GB)
- Use Qwen3 8B Q4_K_M (~6GB) -- can run concurrently
- Add pyannote diarization in post-processing

**If accuracy is paramount (slower is OK):**
- Use faster-whisper large-v3 (INT8, ~3.1GB)
- Add dental vocabulary via initial_prompt (224 token limit)
- Use Qwen3 8B Q6_K for better quality (~7GB VRAM)
- Add LLM post-correction step for dental terminology

**If real-time streaming matters most:**
- Use faster-whisper base.en or small.en for instant feedback
- VAD-chunked audio (silero-vad splits on silence)
- WebSocket streaming transcription to browser
- Final re-transcription with larger model when appointment ends

---

## VRAM Budget: GTX 1070 Ti (8GB)

| Scenario | Whisper | LLM | Diarization | Total | Feasible? |
|----------|---------|-----|-------------|-------|-----------|
| Sequential (recommended) | large-v3-turbo INT8: 2GB | Qwen3 8B Q4: 6GB | Post-hoc: 2GB | Max 6GB at any time | Yes |
| Concurrent transcribe+LLM | large-v3-turbo INT8: 2GB | Phi-4-mini Q4: 3GB | N/A | ~5GB | Yes |
| Concurrent transcribe+LLM | large-v3-turbo INT8: 2GB | Qwen3 8B Q4: 6GB | N/A | ~8GB | Tight, may OOM |
| All concurrent | large-v3: 3.1GB | Qwen3 8B: 6GB | pyannote: 2GB+ | >11GB | No |

**Recommended approach:** Sequential pipeline -- record audio -> transcribe with Whisper -> diarize with pyannote -> structure with LLM. Each step loads/unloads its model. Safer and more predictable on 8GB VRAM.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| faster-whisper >=1.1.0 | PyTorch >=2.0, CUDA 11.8/12.x | Requires CTranslate2 backend |
| silero-vad >=6.0 | PyTorch >=1.12 | ONNX Runtime now optional (v6.2.1) |
| pyannote-audio >=4.0 | PyTorch >=2.0, CUDA 11.8/12.x | v4.0.3+ uses more VRAM than 3.x -- monitor carefully |
| Ollama 0.9.x | CUDA 11.7+ | Auto-detects GPU, no manual CUDA config needed |
| torch + CUDA 12.1 | faster-whisper, silero-vad, pyannote | Use cu121 index for all PyTorch installs |
| sounddevice 0.5.x | numpy >=1.20 | Needs PortAudio (bundled on Windows) |

**Critical:** Install PyTorch with CUDA 12.1 from the cu121 index URL. Mixing CUDA versions between packages causes silent failures.

---

## Dental-Specific Considerations

### Whisper Vocabulary Hints

faster-whisper supports `initial_prompt` (max 224 tokens) for vocabulary biasing. Populate with dental terms:

```python
DENTAL_PROMPT = """
Dental examination. CDT codes: D0120, D0150, D0210, D0220, D0274, D0330,
D1110, D1120, D2140, D2150, D2160, D2330, D2331, D2332, D2335, D2391,
D2392, D2393, D2394, D2740, D2750, D2751, D2752, D3310, D3320, D3330,
D4341, D4342, D4355, D4381, D4910, D5110, D5120, D6010, D6065, D6240,
D7140, D7210, D7220, D7230, D7240, D7241, D8080, D9110, D9230, D9310.
Teeth numbered 1 through 32. Surfaces: mesial, distal, buccal, lingual,
occlusal, incisal, facial. Tooth 14 MOD composite. Tooth 30 DO amalgam.
Bitewing radiographs. Periapical radiograph. Panoramic. CBCT.
Periodontal probing. Bleeding on probing. Class I, II, III, IV, V.
Lidocaine, articaine, septocaine. Composite resin, amalgam, ceramic.
Crown, bridge, implant, extraction, root canal, scaling, root planing.
Gingivitis, periodontitis, caries, abscess, fracture.
"""
```

### LLM Prompt Engineering for SOAP Notes

The LLM (Qwen3 8B) needs a structured system prompt that outputs Dentrix-compatible note format. Use Ollama's JSON schema mode to enforce structure:

```python
SOAP_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "ALL CAPS procedure codes"},
        "chief_complaint": {"type": "string"},
        "clinical_findings": {"type": "string"},
        "treatment_plan": {"type": "string"},
        "procedure_details": {"type": "string"},
        "followup": {"type": "string"}
    },
    "required": ["title", "chief_complaint", "clinical_findings"]
}
```

### Audio Challenges in Dental Environment

| Challenge | Solution |
|-----------|----------|
| Dental drill noise (high-frequency whine) | noisereduce stationary mode + bandpass filter (300Hz-8kHz) |
| Suction device (continuous broadband noise) | noisereduce non-stationary mode |
| Masked speech (dentist/patient wearing masks) | larger Whisper model (large-v3-turbo), initial_prompt with vocabulary |
| Multiple speakers | pyannote diarization post-hoc, label dentist vs patient |
| Short utterances during procedures | silero-vad with lower threshold (0.3-0.4) to catch brief speech |

---

## Sources

- [SYSTRAN/faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- model sizes, compute types, benchmarks (HIGH confidence)
- [snakers4/silero-vad GitHub](https://github.com/snakers4/silero-vad) -- v6.2.1, features, requirements (HIGH confidence)
- [pyannote/pyannote-audio GitHub](https://github.com/pyannote/pyannote-audio) -- v4.0.4, diarization pipeline (HIGH confidence)
- [pyannote VRAM issue #1963](https://github.com/pyannote/pyannote-audio/issues/1963) -- v4.0.3 uses 6x more VRAM than 3.3.2 (HIGH confidence)
- [Ollama qwen3:8b](https://ollama.com/library/qwen3:8b) -- model specs, 5.2GB Q4_K_M (HIGH confidence)
- [Qwen3-8B HuggingFace](https://huggingface.co/Qwen/Qwen3-8B) -- 32K context, architecture (HIGH confidence)
- [Ollama structured outputs blog](https://ollama.com/blog/structured-outputs) -- JSON schema mode (HIGH confidence)
- [Best Local LLMs for 8GB VRAM 2025](https://localllm.in/blog/best-local-llms-8gb-vram-2025) -- VRAM budgets, model comparison (MEDIUM confidence)
- [Picovoice VAD Comparison 2025](https://picovoice.ai/blog/best-voice-activity-detection-vad-2025/) -- Silero vs WebRTC benchmarks (MEDIUM confidence)
- [Whisper Large V3 Turbo HuggingFace](https://huggingface.co/openai/whisper-large-v3-turbo) -- turbo architecture, 4 decoder layers (HIGH confidence)
- [Oral Health Group: AI transcription dental](https://www.oralhealthgroup.com/clinical/dental-research/ai-transcription-tools-could-streamline-dental-record-keeping-kings-study-finds-but-caution-urged-1003990429) -- dental Whisper accuracy study (MEDIUM confidence)
- [Whisper prompting guide (OpenAI Cookbook)](https://cookbook.openai.com/examples/whisper_prompting_guide) -- initial_prompt usage (HIGH confidence)
- [WhisperLive GitHub](https://github.com/collabora/WhisperLive) -- real-time streaming architecture (MEDIUM confidence)
- [Tauri vs Electron for AI apps](https://aiechoes.substack.com/p/building-production-ready-desktop) -- memory overhead comparison (MEDIUM confidence)
- [timsainb/noisereduce GitHub](https://github.com/timsainb/noisereduce) -- spectral gating, PyTorch backend (HIGH confidence)
- [Tom's Hardware Whisper GPU benchmarks](https://www.tomshardware.com/news/whisper-audio-transcription-gpus-benchmarked) -- GTX 1070 performance data (MEDIUM confidence)

---
*Stack research for: local-first ambient clinical dental note-taking*
*Researched: 2026-03-05*
