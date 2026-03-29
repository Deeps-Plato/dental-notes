# Stack Research: v2.0 Production & Clinical

**Domain:** Ambient dental clinical intelligence -- production hardening and clinical enhancements
**Researched:** 2026-03-28
**Confidence:** MEDIUM-HIGH
**Scope:** NEW stack additions only. Existing validated stack (Python 3.12, FastAPI+HTMX, faster-whisper, Ollama/Qwen3, sounddevice, silero-vad, pydantic-settings, sse-starlette, pynput) is not re-researched.

---

## Executive Summary

The v2.0 features split into four distinct capability domains, each requiring different stack additions:

1. **Windows packaging & deployment** (installer, auto-start, multi-machine) -- PyInstaller + Inno Setup + Windows Task Scheduler
2. **Error recovery** (GPU crashes, mic disconnects, Ollama failures) -- tenacity + stdlib only
3. **Enhanced clinical intelligence** (3-way speaker ID, expanded vocabulary, patient summary, templates) -- resemblyzer for speaker embeddings + expanded faster-whisper hotwords/initial_prompt (no new heavy deps)
4. **Batch workflow & auto-pause/resume** -- pure application logic, no new dependencies

The overarching constraint is VRAM: GTX 1050 (4GB) is the floor, and Whisper + Ollama already require sequential GPU handoff. Any new GPU-consuming model is a non-starter unless it can run on CPU or shares the handoff pattern. This rules out pyannote-audio for speaker diarization and points to a lighter approach.

---

## Recommended Stack Additions

### Windows Packaging & Deployment

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PyInstaller | >=6.19.0 | Bundle Python + deps into Windows executable | Eliminates "install Python" requirement for dental office PCs. Version 6.19.0 supports Python 3.12, actively maintained (March 2026 release). Creates a single `dist/` folder with all dependencies. |
| Inno Setup | 6.x | Create professional Windows installer from PyInstaller output | Free, mature (since 1997), generates .exe installer with Start Menu shortcuts, uninstaller, and post-install scripts. Simpler scripting than NSIS. Pascal scripting for custom logic. Produces a single setup.exe that non-technical staff can double-click. |
| pywin32 | >=310 | Windows Task Scheduler integration for auto-start | Provides `win32com.client` for programmatic Task Scheduler registration. Build 310+ supports Python 3.12. Used only during install to register the auto-start task -- not a runtime dependency for the app itself. |

**Why NOT a Windows Service:** A Windows service runs in Session 0 (no desktop interaction, no audio devices, no GPU access). The dental-notes app needs microphone access and CUDA GPU -- both require a user session. Use Windows Task Scheduler with "Run at log on" trigger instead. This matches the proven whisper-ptt approach.

**Why NOT PyInstaller alone (without Inno Setup):** PyInstaller produces a folder of files. An Inno Setup installer adds: one-click install, Start Menu shortcut, auto-start task registration, uninstaller, and upgrade-in-place capability. The dental staff will not interact with raw folders.

**Why NOT NSIS:** NSIS has more complex scripting syntax. Inno Setup uses Pascal scripting which is simpler for the custom steps needed (create Task Scheduler entry, check CUDA availability, register firewall rules for LAN access).

**Why NOT Tauri / Electron wrappers:** The app is already a FastAPI web server with HTMX frontend. Wrapping it in a desktop framework adds complexity for zero benefit. The browser is the UI. Just auto-launch `http://localhost:8000` after server start.

**Confidence:** HIGH for PyInstaller + Inno Setup approach. MEDIUM for pywin32 Task Scheduler integration (proven pattern from whisper-ptt but needs testing with the dental-notes service).

### Error Recovery

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| tenacity | >=9.1.0 | Retry logic with exponential backoff for transient failures | Apache 2.0 licensed, 9.1.4 is latest (Feb 2026). Decorators for retry-on-exception with configurable backoff, jitter, and exception filtering. Perfect for Ollama connection failures and GPU CUDA errors that resolve on retry. Supports async. No heavy dependencies. |

**What tenacity handles:**
- **Ollama failures:** Connection refused (Ollama not started), timeout, model load errors. Retry with exponential backoff up to 3 attempts.
- **GPU/CUDA errors:** Transient CUDA OOM or illegal memory access. Unload model, wait, retry.
- **Mic disconnects:** sounddevice raises PortAudioError. Catch, wait for reconnect, retry stream open.

**What does NOT need tenacity (use stdlib instead):**
- **Session state recovery:** The existing SessionManager state machine with thread lock handles this. Add a `recover()` method that resets to IDLE and cleans up resources.
- **Whisper model reload:** Already has `unload()` + `load_model()`. Wrap in try/except, not retry decorator.
- **Health check endpoint:** New `/api/health` route returning service status (Whisper loaded, Ollama reachable, mic available). Pure FastAPI, no library needed.

**Why NOT circuit-breaker libraries (pybreaker, etc.):** Overkill. The failure modes are transient (GPU hiccup, Ollama restart, mic replug). Simple retry with backoff is sufficient. Circuit breakers add complexity for distributed systems, which this is not.

**Confidence:** HIGH -- tenacity is the standard Python retry library, well-tested, minimal footprint.

### 3-Way Speaker Identification

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| resemblyzer | >=0.1.3 | Lightweight speaker embedding extraction | Runs on CPU at 1000x real-time speed. Extracts 256-dimensional speaker embeddings from audio. Under 50MB model size. No GPU required, no VRAM cost. Can cluster 3 speakers (doctor/patient/assistant) from short audio segments using cosine similarity + simple clustering. |
| scikit-learn | >=1.5.0 | Clustering speaker embeddings | AgglomerativeClustering or KMeans on resemblyzer embeddings. Already a standard scientific Python library. Minimal additional footprint since numpy is already installed. |

**Architecture for 3-way speaker ID:**

The approach is a hybrid: text-based keyword classification (existing) + audio-based speaker embeddings (new). This avoids replacing the working system while adding the ability to distinguish 3 speakers.

1. **Enrollment phase** (first 30 seconds): Doctor speaks known clinical phrases. System captures embeddings for the "doctor" voice. Optionally enroll assistant voice. Patient is the "other" cluster.
2. **Runtime**: For each audio chunk, extract speaker embedding via resemblyzer (CPU, ~1ms per chunk). Compare against enrolled embeddings via cosine similarity. Assign speaker label.
3. **Fallback**: If resemblyzer confidence is low (cosine < 0.7), fall back to existing text-based keyword classifier.
4. **Post-extraction refinement**: LLM SpeakerReattributor (existing) runs on full transcript after recording stops, correcting any misattributions.

**Why NOT pyannote-audio:**
- pyannote-audio 3.1 uses 6-14GB VRAM depending on audio length. The GTX 1050 (4GB) cannot run it alongside anything else.
- pyannote-audio 4.0.3 uses 6x more VRAM than 3.3.2 (9.5GB+ peak). Absolutely not viable on 4-8GB GPUs.
- Even on CPU, pyannote-audio is slow and memory-hungry for real-time use.
- The dental office scenario is 2-3 known speakers, not an unknown number -- overkill to use a full diarization system.

**Why NOT Picovoice Falcon:**
- Free tier limited to 250 minutes/month. A dental office with 5-10 patients/day at 15-30 minutes each would hit 75-300 minutes/day. Commercial pricing starts at $6000/year.
- Requires API key and Picovoice account (even for on-device). Adds an external dependency.
- The dental scenario is simple enough for resemblyzer embeddings + clustering.

**Why NOT diart (streaming pyannote):**
- Built on top of pyannote-audio, inherits the VRAM problem.
- 500ms latency steps add complexity to the existing streaming pipeline.

**Why resemblyzer over SpeechBrain ECAPA-TDNN:**
- Resemblyzer is lighter (single model file, ~50MB vs SpeechBrain's larger ecosystem).
- SpeechBrain pulls in a much larger dependency tree.
- For 3 known speakers in a controlled environment (dental office), resemblyzer's GE2E-based embeddings are sufficient. SpeechBrain would be the right choice for large-scale or high-accuracy requirements.
- Resemblyzer runs on Raspberry Pi. It will absolutely work on these desktop machines.

**Confidence:** MEDIUM -- resemblyzer is proven for speaker verification/clustering, but the specific 3-way dental office scenario (overlapping speech, dental drill noise, mask-muffled speech) needs empirical validation. The text-based fallback provides a safety net.

### Expanded Whisper Vocabulary

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| (no new dependency) | -- | Expanded `initial_prompt` + `hotwords` parameter | faster-whisper already supports both `initial_prompt` (currently used) and `hotwords` (not yet used). The `hotwords` parameter provides hint phrases that boost recognition during beam search decoding. Adding dental-specific hotwords alongside the existing initial_prompt gives two complementary vocabulary guidance mechanisms. |

**What changes (code, not deps):**
- Expand `DENTAL_INITIAL_PROMPT` in `whisper_service.py` with additional terminology categories: pathology terms (leukoplakia, lichen planus, mucocele), anatomy (mandibular canal, mental foramen, maxillary sinus), findings (radiopaque, radiolucent, dehiscence, fenestration), diagnoses (pulpitis, pericoronitis, temporomandibular disorder), materials (Herculite, Estelite, Paracore, Luxatemp).
- Add `hotwords` parameter to `transcribe()` call with the most frequently misrecognized dental terms. The `hotwords` parameter is `Optional[str]` and provides complementary boosting to `initial_prompt`.
- Make the vocabulary configurable via `Settings` so templates can pass procedure-specific terms (e.g., endo appointments boost "working length", "obturation", "gutta-percha").

**Important limitation:** The `hotwords` parameter "has no effect if prefix is not None" per faster-whisper source. Since we do not use `prefix`, this is fine for our use case.

**Confidence:** HIGH -- initial_prompt is already proven in the codebase. hotwords parameter verified in faster-whisper source code.

### Appointment Templates & Patient Summary

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| (no new dependency) | -- | Template-specific prompts and patient summary generation | Appointment templates are Pydantic models + Jinja2 template variations. Patient summary is a second LLM extraction pass with a patient-facing system prompt. Both use existing Ollama infrastructure. |

**What changes (code, not deps):**
- New `AppointmentTemplate` Pydantic model with template name, expected sections, procedure-specific vocabulary, and extraction prompt overrides.
- Template selection in UI before recording start. Template flows into: (a) Whisper hotwords, (b) extraction system prompt, (c) review page layout.
- Patient summary: second `OllamaService.generate_structured()` call with a "plain language patient education" system prompt, reusing the same transcript. Runs during the existing GPU handoff window (after SOAP extraction, before Whisper reload).

**Confidence:** HIGH -- pure application logic on top of existing infrastructure.

### Batch Workflow & Auto-Pause/Resume

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| (no new dependency) | -- | Multi-session management with silence-gap detection | The existing SessionManager, SessionStore, and silero-vad provide all primitives needed. Batch workflow is a state machine extension. Auto-pause uses the existing VAD silence detection with a longer gap threshold (e.g., 60 seconds of silence = auto-pause). |

**What changes (code, not deps):**
- Extend `SessionManager` state machine: `RECORDING -> AUTO_PAUSED` on extended silence. `AUTO_PAUSED -> RECORDING` on speech detection.
- New `BatchSession` concept wrapping multiple `SavedSession`s with a daily workflow (morning start, auto-pause between patients, evening review).
- Session metadata: appointment start time, appointment type, consent acknowledgment.

**Confidence:** HIGH -- extends existing patterns, no new technology.

---

## Full Stack (Existing + New)

### Existing (validated, DO NOT change)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Application language |
| FastAPI | >=0.135.0 | HTTP API + web server |
| HTMX + Jinja2 | 2.0 / >=3.1.0 | Web UI |
| faster-whisper | >=1.0.3 | Local Whisper transcription (CTranslate2) |
| silero-vad | >=5.1 | Voice activity detection |
| sounddevice | >=0.5.0 | Audio capture |
| numpy | >=1.26.0 | Array operations |
| Ollama (ollama Python pkg) | >=0.6.1 | Local LLM inference (Qwen3 8B/4B) |
| pydantic-settings | >=2.3.0 | Configuration management |
| sse-starlette | >=2.0.0 | Server-sent events for streaming |
| pynput | >=1.7.6 | Keyboard/mouse hotkeys |
| uvicorn | >=0.30.0 | ASGI server |

### New Additions (v2.0)

| Technology | Version | Purpose | Feature Area |
|------------|---------|---------|-------------|
| PyInstaller | >=6.19.0 | Bundle into Windows executable | Installer |
| Inno Setup | 6.x (external tool) | Create .exe installer | Installer |
| pywin32 | >=310 | Task Scheduler auto-start registration | Auto-start |
| tenacity | >=9.1.0 | Retry with exponential backoff | Error recovery |
| resemblyzer | >=0.1.3 | Speaker embedding extraction (CPU) | 3-way speaker ID |
| scikit-learn | >=1.5.0 | Clustering for speaker ID | 3-way speaker ID |

---

## Installation

```bash
# Existing deps (unchanged)
pip install "fastapi[standard]>=0.135.0" uvicorn>=0.30.0 pydantic-settings>=2.3.0
pip install jinja2>=3.1.0 sse-starlette>=2.0.0 pynput>=1.7.6
pip install faster-whisper>=1.0.3 silero-vad>=5.1 sounddevice>=0.5.0
pip install numpy>=1.26.0 ollama>=0.6.1

# NEW: v2.0 additions
pip install tenacity>=9.1.0          # Error recovery (retry logic)
pip install resemblyzer>=0.1.3       # Speaker embeddings (CPU)
pip install scikit-learn>=1.5.0      # Clustering for speaker ID
pip install pywin32>=310             # Windows Task Scheduler (install-time only)

# NEW: Build/packaging (dev machine only, not on office PCs)
pip install pyinstaller>=6.19.0

# Inno Setup: Download from https://jrsoftware.org/isdl.php (Windows GUI tool)
# Not a pip package. Install on the build machine only.

# Dev dependencies (unchanged)
pip install pytest>=8.2.0 pytest-cov pytest-asyncio>=0.23.0
pip install httpx>=0.27.0 ruff>=0.5.0 mypy>=1.10.0
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| PyInstaller + Inno Setup | cx_Freeze + NSIS | If PyInstaller has insurmountable issues with CUDA/CTranslate2 bundling. cx_Freeze handles some edge cases differently. NSIS is more flexible but harder to script. |
| PyInstaller + Inno Setup | Pynsist | If you want NSIS-based installer without writing NSIS scripts. Bundles Python itself. Good for simple apps but less control over CUDA dependency handling. |
| PyInstaller (--onedir) | PyInstaller (--onefile) | Never use --onefile for this app. Single-file bundles extract to temp dir on every launch (slow startup, ~10s+ for torch), CUDA libraries may fail to load from temp paths, and antivirus false positives are common. Always use --onedir. |
| Windows Task Scheduler | Windows Service (pywin32 win32serviceutil) | Never for this app. Services run in Session 0 with no audio device access and no GPU. Only use if the app were a pure network daemon with no hardware interaction. |
| resemblyzer | pyannote-audio | If you upgrade to 12GB+ VRAM GPUs. pyannote is state-of-the-art for general diarization but needs 6-14GB VRAM. Not viable on 4-8GB. |
| resemblyzer | SpeechBrain ECAPA-TDNN | If resemblyzer accuracy is insufficient for the dental environment. SpeechBrain has better embeddings but heavier dependency tree (full toolkit install). Consider as fallback. |
| resemblyzer | Picovoice Falcon | If budget allows $6000/year and you want turnkey diarization. Better accuracy out of the box but adds commercial dependency and usage limits. |
| tenacity | Custom retry decorator | If you need exactly 2 retries for one function. For anything more complex, tenacity's declarative API is cleaner and battle-tested. |
| Inno Setup | WiX Toolset | If you need MSI packages for enterprise Group Policy deployment. Massive learning curve. Inno Setup .exe is fine for a small dental practice. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pyannote-audio | 6-14GB VRAM, cannot fit on GTX 1050/1070 alongside Whisper. v4.0.3 uses 9.5GB+ peak. | resemblyzer (CPU, <50MB model) + scikit-learn clustering |
| diart (streaming pyannote) | Built on pyannote-audio, inherits VRAM problem. Adds 500ms latency complexity. | resemblyzer with per-chunk embedding extraction |
| Windows Service approach | Session 0 isolation: no mic access, no GPU, no desktop. App requires both. | Windows Task Scheduler "Run at log on" trigger |
| PyInstaller --onefile | Extracts to temp dir on every launch. 10s+ startup for torch. CUDA path issues. Antivirus false positives. | PyInstaller --onedir (folder-based distribution) |
| Electron / Tauri wrapper | App is already a web server + browser UI. Desktop wrapper adds 150MB+ for no benefit. | Launch browser to localhost:8000 after server start |
| AlbumentationsX | AGPL license (from dental-image-ai research). Not relevant here but worth noting if any image features are added. | N/A for this project |
| Docker for deployment | Office PCs run Windows 10 with no Docker. WSL2 + Docker adds complexity and breaks audio/GPU access. | Native Windows Python via PyInstaller |
| PyTorch (as direct dependency) | faster-whisper uses CTranslate2, not PyTorch. resemblyzer brings in torch as a transitive dependency but it runs on CPU. Do NOT install torch with CUDA wheels for resemblyzer -- it will conflict with the CTranslate2 CUDA setup. | Let resemblyzer pull its own torch dependency; use CPU-only torch for speaker embeddings. |

---

## Critical Integration Notes

### VRAM Budget (the binding constraint)

The GTX 1050 (4GB) and GTX 1070 Ti (8GB) cannot run multiple GPU models simultaneously. The existing GPU handoff pattern MUST be maintained:

```
Recording: Whisper on GPU (~1-2GB VRAM for small/int8)
    |
    v [session stop]
    |
Extraction: Whisper unload -> Ollama/Qwen3 on GPU (~4-6GB VRAM)
    |
    v [extraction complete]
    |
Patient Summary: Reuse Ollama (already loaded) -> second LLM call
    |
    v [summary complete]
    |
Cleanup: Ollama unload -> Whisper reload (ready for next session)
```

**resemblyzer runs on CPU throughout** -- no GPU handoff needed. This is why it was chosen over pyannote.

**Patient summary slots into the existing handoff window** -- the LLM is already loaded for SOAP extraction. Adding a second prompt costs only inference time, not additional model loading.

### PyInstaller + CUDA/CTranslate2 Bundling

This is the highest-risk technical area. Known issues:

1. **CTranslate2 CUDA libraries:** PyInstaller may not auto-detect `ctranslate2` CUDA binaries. Add `--collect-all ctranslate2` to PyInstaller spec.
2. **faster-whisper model files:** Whisper models download to `~/.cache/huggingface/`. The installer should pre-download the `small` model and bundle it, or download on first run.
3. **sounddevice/PortAudio:** PyInstaller needs `--collect-binaries sounddevice` to include the PortAudio DLL.
4. **Ollama is separate:** Ollama runs as its own Windows process. The installer should check for Ollama, and either bundle it or prompt the user to install it. Ollama has its own Windows installer.
5. **torch CPU for resemblyzer:** If resemblyzer pulls in torch, ensure it gets CPU-only torch to avoid conflicting with CTranslate2's CUDA. Use `--extra-index-url https://download.pytorch.org/whl/cpu` for the resemblyzer environment.

**Mitigation:** Build the PyInstaller spec file incrementally. Test on a clean Windows VM after each addition. The whisper-standalone-win project (Purfview/whisper-standalone-win on GitHub) is a reference for how to package faster-whisper into a Windows executable.

### Auto-Start Architecture

```
[Inno Setup installer]
    |
    |--> Install files to C:\Program Files\DentalNotes\
    |--> Register Task Scheduler task via pywin32:
    |      Trigger: "At log on" for current user
    |      Action: Run dental-notes.exe (starts FastAPI server)
    |      Settings: Run whether or not user is logged on = NO
    |                Run only when user is logged on = YES
    |--> Create Start Menu shortcut
    |--> Create Desktop shortcut (optional)
    |--> Open http://localhost:8000 in default browser
```

**Why "Run only when user is logged on":** The app needs the user session for audio device access. This matches the whisper-ptt precedent.

### Multi-Machine Deployment

Not a new technology -- it is a deployment process:

1. Build installer on dev machine (one-time PyInstaller + Inno Setup).
2. Copy `DentalNotes_Setup.exe` to each operatory PC via USB drive or shared network folder.
3. Double-click to install. Installer handles: file copy, Task Scheduler registration, Ollama check, first-run model download.
4. Each PC runs independently (no network coordination between PCs).
5. Config file (`dental-notes.toml` or environment variables) per machine for mic device selection.

No central server, no database, no network sync. Each operatory PC is a standalone unit.

---

## Stack Patterns by Feature

**If speaker embedding accuracy is insufficient:**
- Upgrade from resemblyzer to SpeechBrain ECAPA-TDNN
- Still runs on CPU, but larger model (~100MB) and heavier dependency tree
- Requires `pip install speechbrain` which pulls in torch, torchaudio, HuggingFace transformers

**If PyInstaller bundling fails with CUDA/CTranslate2:**
- Fall back to "portable install" approach: bundle Python + venv in a folder via Inno Setup
- Use Pynsist which bundles a Python distribution and creates NSIS installer
- Or use CondaNSIS which packages a full conda environment as an installer
- Worst case: script-based installer (PowerShell) that installs Python + pip deps on the target machine

**If GTX 1050 machines are too constrained:**
- Whisper `tiny` model instead of `small` (less accurate but ~0.5GB VRAM)
- Qwen3 4B instead of 8B for extraction (already a fallback in current code)
- Skip resemblyzer speaker ID on 4GB machines, use text-only classification

**If office wants centralized management:**
- Future consideration, not v2 scope
- Would need a shared config server (simple FastAPI on one PC)
- Not recommended for v2 -- keep each PC independent

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| PyInstaller 6.19.0 | Python 3.12 | Tested and supported. Use --onedir mode. |
| pywin32 >=310 | Python 3.12 | Build 310+ has Python 3.12 wheels. Install via pip. |
| tenacity >=9.1.0 | Python >=3.10 | Pure Python, no binary deps. 9.1.4 latest (Feb 2026). |
| resemblyzer >=0.1.3 | torch (CPU), numpy, scipy, librosa | Pulls in torch as dependency. Force CPU-only torch to avoid CUDA conflicts with CTranslate2. |
| scikit-learn >=1.5.0 | numpy >=1.26, scipy >=1.5 | numpy already in stack. scipy comes with resemblyzer. |
| faster-whisper >=1.0.3 | CTranslate2 (CUDA 12.x) | hotwords parameter available in current versions. Verify no breaking changes if upgrading. |
| Inno Setup 6.x | Windows 7+ | External tool, not a Python dependency. Runs on dev machine only. |

**Critical compatibility warning:** resemblyzer depends on torch. If pip resolves torch with CUDA wheels, it will install ~2.5GB of CUDA libraries that may conflict with CTranslate2's CUDA setup. Force CPU-only torch for the resemblyzer dependency:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install resemblyzer
```

Or in pyproject.toml, specify torch as CPU-only via dependency groups.

---

## pyproject.toml Changes

```toml
[project]
dependencies = [
    # ... existing deps unchanged ...
    "tenacity>=9.1.0",
    "resemblyzer>=0.1.3",
    "scikit-learn>=1.5.0",
]

[project.optional-dependencies]
dev = [
    # ... existing dev deps unchanged ...
    "pyinstaller>=6.19.0",
]
# pywin32 installed separately on Windows only (not cross-platform)
# Inno Setup is an external Windows application, not a pip package
```

---

## Sources

- [PyInstaller 6.19.0 docs](https://pyinstaller.org/en/stable/) -- Python 3.12 support, --onedir mode (HIGH confidence)
- [PyInstaller + FastAPI example](https://github.com/iancleary/pyinstaller-fastapi) -- reference implementation (MEDIUM confidence)
- [Inno Setup official site](https://jrsoftware.org/isinfo.php) -- features, scripting, download (HIGH confidence)
- [pywin32 releases](https://github.com/mhammond/pywin32/releases) -- Build 310+, Python 3.12 wheels (HIGH confidence)
- [Creating Windows service with pywin32 + PyInstaller](https://metallapan.se/post/windows-service-pywin32-pyinstaller/) -- Task Scheduler approach (MEDIUM confidence)
- [tenacity 9.1.4 on PyPI](https://pypi.org/project/tenacity/) -- latest version, Python >=3.10 (HIGH confidence)
- [tenacity docs](https://tenacity.readthedocs.io/) -- retry patterns, exponential backoff (HIGH confidence)
- [resemblyzer on GitHub](https://github.com/resemble-ai/Resemblyzer) -- 1000x real-time on GPU, works on CPU (MEDIUM confidence)
- [resemblyzer on PyPI](https://pypi.org/project/Resemblyzer/) -- version 0.1.3 (MEDIUM confidence)
- [pyannote-audio VRAM issues](https://github.com/pyannote/pyannote-audio/issues/1963) -- 4.0.3 uses 9.54GB+ peak VRAM (HIGH confidence)
- [pyannote-audio 3.1 memory issues](https://github.com/pyannote/pyannote-audio/issues/1580) -- doubles memory vs previous (HIGH confidence)
- [Picovoice Falcon pricing](https://picovoice.ai/pricing/) -- 250 min/month free, $6000/year commercial (HIGH confidence)
- [Picovoice Falcon Python API](https://picovoice.ai/docs/api/falcon-python/) -- on-device, CPU capable (HIGH confidence)
- [faster-whisper transcribe.py source](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py) -- hotwords parameter, initial_prompt (HIGH confidence)
- [Whisper prompting guide (OpenAI)](https://cookbook.openai.com/examples/whisper_prompting_guide) -- initial_prompt best practices (HIGH confidence)
- [PyInstaller + CUDA issues](https://github.com/pyinstaller/pyinstaller/issues/7175) -- known bundling challenges (HIGH confidence)
- [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win) -- reference for packaging faster-whisper on Windows (MEDIUM confidence)
- [Speaker diarization models comparison 2026](https://brasstranscripts.com/blog/speaker-diarization-models-comparison) -- landscape overview (MEDIUM confidence)
- [Lightweight speaker diarization (CPU-only)](https://towardsai.net/p/machine-learning/towards-approximate-fast-diarization-a-cpu-only-alternative-to-pyannote-3-1) -- SpeechBrain ECAPA-TDNN approach (MEDIUM confidence)
- [SpeechBrain ECAPA-TDNN model](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) -- speaker embeddings (MEDIUM confidence)

---
*Stack research for: dental-notes v2.0 production & clinical enhancements*
*Researched: 2026-03-28*
