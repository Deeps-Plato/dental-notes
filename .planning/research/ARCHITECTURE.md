# Architecture Research: v2.0 Feature Integration

**Domain:** Ambient dental clinical intelligence -- local-first audio transcription and SOAP note generation
**Researched:** 2026-03-28
**Confidence:** HIGH (based on deep reading of existing codebase + targeted technology research)

## Executive Summary

The v2.0 features divide cleanly into three tiers of integration complexity with the existing codebase:

1. **Low-touch extensions** that enhance existing components with minimal structural change: expanded Whisper vocabulary, appointment templates, patient summary generation. These modify existing files (whisper_service.py, prompts.py, models.py) without introducing new architectural patterns.

2. **Medium-touch additions** that introduce new components wired into existing lifecycle hooks: batch session management, auto-pause via extended silence detection, 3-way speaker classification, error recovery watchdog. These add new modules and modify SessionManager's state machine and processing loop.

3. **High-touch infrastructure** that operates outside the application boundary: Windows service/installer, auto-start on boot, multi-machine deployment config. These wrap the existing application without modifying its internals.

The 8GB VRAM constraint remains the dominant architectural force. Every feature must be evaluated through the lens of "does this add GPU memory pressure?" Pyannote-based audio diarization is ruled out because pyannote 4.x uses 6-9GB VRAM alone, which is incompatible with the 4-8GB GPU target. The existing text-based + LLM reattribution approach extends naturally to 3-way classification.

## Current Architecture (v1 Baseline)

```
                         FastAPI (main.py)
                              |
           +---------+--------+--------+---------+
           |         |        |        |         |
        routes.py  dictation  SSE    hotkey    lifespan
           |         |      stream   listener    |
           |         |        |        |         |
           v         v        v        v         v
     SessionStore  WhisperSvc  SessionManager   init/shutdown
     (JSON files)  (shared)    (state machine)   (Whisper, Ollama,
                       |            |              SessionStore)
                       |     +------+------+
                       |     |      |      |
                       |  AudioCap  VAD  Chunker
                       |     |      |      |
                       |     +----->+----->|
                       |                   |
                       +<------ transcribe(chunk)
                       |
              ClinicalExtractor
              (GPU handoff: Whisper unload -> LLM -> LLM unload -> Whisper reload)
                       |
              ExtractionResult
              (SoapNote + CDT codes + SpeakerChunks)
```

### Key Architectural Properties

| Property | Current Implementation | v2 Impact |
|----------|----------------------|-----------|
| Session lifecycle | Single active session, IDLE -> RECORDING -> PAUSED -> STOPPING -> IDLE | Must support batch: multiple saved sessions, rapid cycle between patients |
| Audio pipeline | sounddevice -> queue -> VAD -> chunker -> Whisper -> stitcher -> writer | Auto-pause adds silence duration tracking in the processing loop |
| GPU memory | Sequential: Whisper OR LLM, never both (8GB constraint) | No change -- all v2 features must respect this constraint |
| Speaker classification | Text keyword regex (session/speaker.py) + LLM reattribution (clinical/speaker.py) | Extend keyword patterns + LLM prompt for 3-way (Doctor/Patient/Assistant) |
| Extraction prompt | Single monolithic prompt in clinical/prompts.py | Template system selects prompt variant based on appointment type |
| Persistence | JSON files via SessionStore, atomic writes | Add appointment_type + metadata fields to SavedSession |
| Error handling | Try/except at route level, graceful degradation (Ollama optional) | Watchdog wraps entire process, per-component health checks |
| Deployment | Manual `pip install` + `python -m dental_notes.main` | NSSM service wrapper + install script |

## v2 Component Integration Map

### Feature-to-File Impact Matrix

This is the core reference for implementation. Each row is a v2 feature; columns show which existing files are modified (M) and which new files are created (N).

| Feature | session/manager.py | session/store.py | clinical/prompts.py | clinical/models.py | clinical/extractor.py | transcription/whisper_service.py | session/speaker.py | config.py | main.py | ui/routes.py | New Files |
|---------|-------------------|-----------------|--------------------|--------------------|----------------------|--------------------------------|-------------------|-----------|---------|-------------|-----------|
| Batch workflow | M (auto-save on stop) | M (metadata fields) | - | - | - | - | - | M (batch settings) | - | M (batch UI routes) | templates: batch dashboard |
| Auto-pause/resume | M (silence counter in _processing_loop) | - | - | - | - | - | - | M (auto_pause_silence_secs) | - | M (SSE pause events) | - |
| Appointment templates | - | M (appointment_type field) | M (template variants) | M (appointment_type enum) | M (template selection) | - | - | - | - | M (type selector in UI) | clinical/templates.py (N) |
| 3-way speaker ID | - | - | M (3-way attribution prompt) | M (speaker enum: Doctor/Patient/Assistant) | - | - | M (assistant patterns) | - | - | - | - |
| Expanded Whisper vocab | - | - | - | - | - | M (extended DENTAL_INITIAL_PROMPT + hotwords) | - | M (hotwords setting) | - | - | - |
| Patient summary | - | M (patient_summary field) | M (summary prompt) | M (PatientSummary model) | M (summary generation method) | - | - | - | - | M (summary in review) | clinical/summary.py (N) or inline |
| Windows installer | - | - | - | - | - | - | - | - | - | - | install.py (N), nssm config, setup script |
| Auto-start on boot | - | - | - | - | - | - | - | - | - | - | service wrapper config |
| Error recovery | - | - | - | - | - | M (health check method) | - | M (watchdog settings) | M (health endpoint) | M (health status route) | watchdog.py (N), health.py (N) |
| Multi-machine config | - | - | - | - | - | - | - | M (config file path, machine_id) | - | - | deploy/ directory (N) |

### New Components Needed

| Component | Location | Responsibility | Depends On |
|-----------|----------|---------------|------------|
| `clinical/templates.py` | src/dental_notes/clinical/ | Appointment-type prompt templates (exam, restorative, hygiene, endo, extraction) | clinical/prompts.py (imports base prompt sections) |
| `watchdog.py` | src/dental_notes/ | Process supervisor: heartbeat monitoring, component health checks, auto-restart on failure | main.py (wraps the FastAPI process) |
| `health.py` | src/dental_notes/ | Health check aggregator: GPU status, Ollama reachability, mic availability, disk space | config.py, whisper_service.py, ollama_service.py |
| `install.py` | project root | Windows installer script: checks prerequisites, installs deps, configures NSSM service, creates shortcuts | NSSM binary, config.py |
| `deploy/` | project root | Multi-machine deployment configs, per-machine settings templates | config.py |

## Detailed Integration Analysis by Feature

### 1. Batch Session Management

**What changes:** SessionManager.stop() currently returns a Path and the route creates a SavedSession. For batch workflow, the stop-and-start cycle needs to be fast -- the user records Patient A, clicks "Next Patient", and the system saves session A and starts a new session for Patient B without navigating away from the recording screen.

**Existing code affected:**
- `session/manager.py`: No structural change needed. The existing stop() -> IDLE -> start() cycle already works. The UI orchestrates the batch flow.
- `session/store.py`: Add fields to `SavedSession`: `appointment_type: str | None`, `patient_label: str | None` (anonymous label like "Patient 3" -- no PHI), `batch_date: date | None`.
- `ui/routes.py`: Add `POST /session/next-patient` route that chains stop + create_session + start in one request. Add `GET /batch` dashboard route showing today's sessions with status.
- Templates: New batch dashboard template showing today's sessions as cards with status indicators.

**Data flow change:**
```
Current:  Start -> Record -> Stop -> [navigate to review] -> Extract -> Review -> Finalize
Batch v2: Start -> Record -> "Next Patient" -> [auto-save, auto-start new session]
                                                -> ... repeat per patient ...
                                             -> "End Day" -> [navigate to batch dashboard]
                                             -> [click each session] -> Extract -> Review -> Finalize
```

**VRAM impact:** None. Batch is a UI/persistence concern, not a GPU concern.

### 2. Auto-Pause via Extended Silence Detection

**What changes:** The processing loop in `SessionManager._processing_loop()` already tracks silence via the chunker's `_silence_samples` counter. Auto-pause extends this: if silence exceeds a configurable threshold (e.g., 120 seconds), the session automatically pauses and sends an SSE event to the UI.

**Existing code affected:**
- `session/manager.py`: Add `_continuous_silence_secs: float` counter in `_processing_loop()`. When VAD reports no speech for `auto_pause_silence_secs` consecutive seconds, call `self.pause()` internally (using the lock). Add `_auto_paused: bool` flag to distinguish user-pause from auto-pause.
- `config.py`: Add `auto_pause_silence_secs: float = 120.0` and `auto_pause_enabled: bool = True`.
- `ui/routes.py`: SSE stream should emit an `auto_pause` event so the UI can show "Paused -- waiting for next patient" vs "Paused by user".

**Key implementation detail:** The silence counter must reset on any speech detection. The counter increments by `block_duration_secs` for each non-speech block. This is a ~10-line change in `_processing_loop()`.

```python
# In _processing_loop, after VAD check:
if is_speech:
    self._continuous_silence_secs = 0.0
else:
    self._continuous_silence_secs += block_samples / self._settings.sample_rate
    if (self._settings.auto_pause_enabled
            and self._continuous_silence_secs >= self._settings.auto_pause_silence_secs
            and self._state == SessionState.RECORDING):
        with self._lock:
            if self._state == SessionState.RECORDING:
                self._capture.stop()
                self._state = SessionState.PAUSED
                self._auto_paused = True
                logger.info("Auto-paused after %.0fs silence", self._continuous_silence_secs)
```

**Auto-resume:** When audio resumes (user clicks resume or speaks near mic), the session resumes. Auto-resume on speech detection is complex (mic is stopped during pause -- no audio to detect). Simpler: manual resume via UI button or hotkey. The auto-pause saves power/resources between patients but requires manual resume, which is fine for the clinical workflow (dentist calls next patient, seats them, gets ready, then explicitly starts/resumes recording).

**VRAM impact:** None. VAD runs on CPU.

### 3. Appointment Templates in Extraction Prompts

**What changes:** The current `EXTRACTION_SYSTEM_PROMPT` in `clinical/prompts.py` is a monolithic string. Appointment templates customize the extraction prompt based on procedure type, so the LLM produces notes structured appropriately for each type.

**Design approach:** Template composition, not template replacement. A base prompt (the current one) covers universal SOAP structure. Template overlays add type-specific sections, field emphasis, and CDT code subsets.

**New file: `clinical/templates.py`**

```python
from enum import Enum

class AppointmentType(str, Enum):
    EXAM = "exam"
    RESTORATIVE = "restorative"
    HYGIENE = "hygiene"
    ENDO = "endo"
    EXTRACTION = "extraction"
    GENERAL = "general"  # default, uses base prompt only

# Each template adds type-specific instructions appended to the base prompt
TEMPLATE_OVERLAYS: dict[AppointmentType, str] = {
    AppointmentType.EXAM: """
## Appointment Type: Comprehensive/Periodic Exam
Focus on: findings per tooth/area, radiographic interpretation, treatment plan.
Objective section should be thorough -- document every finding mentioned.
CDT codes: always include exam code (D0120/D0150) and any radiographs taken.
""",
    AppointmentType.RESTORATIVE: """
## Appointment Type: Restorative Procedure
Focus on: procedure steps, materials, shade, anesthetic details.
Objective must include: tooth prep, material placement, occlusal check.
Include procedure documentation subsection (consent, anesthetic, steps, post-op).
CDT codes: restoration code with correct surface count + any additional services.
""",
    # ... etc for each type
}
```

**Existing code affected:**
- `clinical/prompts.py`: Refactor to expose `build_extraction_prompt(appointment_type: AppointmentType) -> str` that combines base + overlay.
- `clinical/extractor.py`: `extract()` and `extract_with_gpu_handoff()` accept optional `appointment_type` parameter, pass to prompt builder.
- `clinical/models.py`: Add `AppointmentType` enum (or import from templates).
- `session/store.py`: Add `appointment_type: str | None = None` to `SavedSession`.
- `ui/routes.py`: Session start accepts appointment type selection; extraction passes it through.

**VRAM impact:** None. Longer prompts consume more context window but not GPU memory beyond what Ollama already allocates.

### 4. 3-Way Speaker Classification (Doctor/Patient/Assistant)

**What changes:** The existing two-tier classification (keyword regex in `session/speaker.py` + LLM reattribution in `clinical/speaker.py`) extends to three speakers. This is text-based -- no audio diarization model needed.

**Why NOT pyannote/audio diarization:**
- pyannote 4.x uses 6-9GB VRAM peak (issue #1963 on pyannote-audio GitHub). The target hardware is 4-8GB GPU, already shared between Whisper and Ollama.
- pyannote 3.1 uses ~1.6GB VRAM, but would need to run concurrently with Whisper (both need GPU during recording). The sequential GPU handoff pattern cannot accommodate three models.
- CPU-only pyannote is possible but adds 1.5+ minutes processing per 90-minute file -- too slow for near-real-time streaming.
- The text-based approach works well enough for dental context where speakers have very distinct vocabularies, and LLM reattribution already corrects misclassifications.

**Existing code affected:**
- `session/speaker.py`: Add `_ASSISTANT_PATTERNS` list. Assistants use phrases like "suction", "pass me the", "retract", "mixing", "light cure", "prep the", "the tray is ready". Extend `classify_speaker()` to return "Doctor", "Patient", or "Assistant" with 3-way scoring.
- `clinical/speaker.py`: Update `SPEAKER_SYSTEM_PROMPT` to include Assistant attribution rules. Add "Assistant: relays instruments, follows doctor's directives, confirms readiness, handles suction/retraction, uses short acknowledgments during procedures" to the rules.
- `clinical/models.py`: Change `SpeakerChunk.speaker` field description from "Doctor or Patient" to "Doctor, Patient, or Assistant". No schema change needed -- it is already a `str` field.
- `clinical/prompts.py`: Update EXTRACTION_SYSTEM_PROMPT speaker attribution rules section to include Assistant.

**VRAM impact:** None. Text classification is CPU-only. LLM reattribution uses the same Ollama call with a slightly longer prompt.

### 5. Expanded Whisper Dental Vocabulary

**What changes:** The existing `DENTAL_INITIAL_PROMPT` in `whisper_service.py` is already comprehensive (covers tooth numbering, surfaces, restorative, perio, endo, surgery, implants, materials, CDT codes, clinical terms). v2 expands this with additional categories and leverages faster-whisper's `hotwords` parameter for targeted boosting.

**Existing code affected:**
- `transcription/whisper_service.py`: Expand `DENTAL_INITIAL_PROMPT` with additional vocabulary categories. Add `hotwords` parameter to `transcribe()` call. Faster-whisper supports `hotwords` as a comma-separated string that boosts recognition probability for specific terms.
- `config.py`: Add `whisper_hotwords: str = ""` setting for user-customizable hotwords beyond the built-in prompt.

**New vocabulary categories to add:**
- Pathology: "pericoronitis, cellulitis, osteomyelitis, leukoplakia, lichen planus, aphthous ulcer, mucocele, fibroma, papilloma, ameloblastoma"
- Anatomy: "maxillary, mandibular, alveolar ridge, ramus, condyle, frenulum, vestibule, palatal, labial, interproximal"
- Findings: "fremitus, suppuration, exudate, fistula, dehiscence, fenestration, ankylosis"
- Diagnoses: "reversible pulpitis, irreversible pulpitis, pulp necrosis, cracked tooth syndrome, vertical root fracture"
- Surfaces expanded: "distolingual, mesiobuccal, distobuccal, mesiolingual"
- Materials expanded: "Fuji, GC, Herculite, Empress, BruxZir, CEREC, Procera"
- Instruments: "explorer, scaler, curette, handpiece, bur, articulating paper"
- Procedures expanded: "hemisection, apicoectomy, pulp cap, sedative fill, temporary crown"

**Implementation detail:**
```python
# In transcribe():
segments, _ = self._model.transcribe(
    audio,
    initial_prompt=DENTAL_INITIAL_PROMPT,
    hotwords=self._settings.whisper_hotwords or None,  # NEW
    vad_filter=True,
    no_speech_threshold=0.6,
    language="en",
)
```

**VRAM impact:** None. initial_prompt and hotwords are text tokens processed during decoding, not stored in GPU memory.

### 6. Patient Summary Generation

**What changes:** After SOAP note extraction, a second LLM call generates a plain-language patient summary suitable for patient handouts. This was deferred from v1 Phase 3 (REV-04).

**Design approach:** Separate LLM call after SOAP extraction (not combined) because the summary prompt is fundamentally different -- it must avoid medical jargon and be written at an 8th-grade reading level. Running it as a second call reuses the same GPU handoff window (Whisper is already unloaded).

**Existing code affected:**
- `clinical/models.py`: Add `PatientSummary` model with fields: `summary: str`, `next_steps: list[str]`, `questions_to_ask: list[str]`.
- `clinical/extractor.py`: Add `generate_patient_summary(soap_note: SoapNote) -> PatientSummary` method. Runs after extract() within the same GPU handoff window (Whisper still unloaded). The sequence becomes: Whisper unload -> extract SOAP -> generate summary -> LLM unload -> Whisper reload.
- `clinical/prompts.py`: Add `PATIENT_SUMMARY_PROMPT` -- plain language, no jargon, 8th-grade reading level, empathetic tone.
- `session/store.py`: Add `patient_summary: PatientSummary | None = None` to SavedSession.
- `ui/routes.py`: Review page includes summary section. Summary can be regenerated independently.
- Templates: Add summary panel to review page (collapsible, below or beside SOAP note).

**GPU handoff sequence change:**
```
v1:  Whisper.unload() -> LLM.extract() -> LLM.unload() -> Whisper.reload()
v2:  Whisper.unload() -> LLM.extract() -> LLM.summarize() -> LLM.unload() -> Whisper.reload()
```

The summary call adds ~10-15 seconds to extraction time but avoids an extra GPU handoff cycle.

**VRAM impact:** None additional. Uses the same Ollama model already loaded for extraction.

### 7. Windows Service/Installer

**What changes:** Currently the server is started manually with `python -m dental_notes.main`. v2 wraps this as a Windows service that starts on boot and restarts on crash.

**Recommended approach: NSSM (Non-Sucking Service Manager)** over pywin32 service class because:
- NSSM wraps any executable as a service without code changes to the application
- Built-in crash recovery (auto-restart on unexpected exit)
- Logging redirection to files with rotation
- No need to bundle NSSM into PyInstaller -- it is a standalone 300KB .exe
- Proven in production for Python services

**Why NOT PyInstaller bundling:** The application depends on CUDA, cuDNN, faster-whisper (CTranslate2), PyTorch (for silero-vad), and Ollama. Bundling CUDA DLLs into PyInstaller adds ~400MB+ to the installer, creates version conflicts with system CUDA, and makes debugging GPU issues nearly impossible. The target machines already have CUDA installed (GTX 1050+ with drivers). A pip-based install with NSSM service wrapper is dramatically simpler.

**New files:**
- `install.py`: Installation script that:
  1. Checks prerequisites (Python 3.12, CUDA, Ollama)
  2. Creates a virtualenv in a standard location (e.g., `C:\DentalNotes\`)
  3. Installs pip dependencies (including CUDA PyTorch)
  4. Pulls Ollama model (qwen3:8b or qwen3:4b based on GPU)
  5. Installs NSSM service pointing to the venv's python + main.py
  6. Sets service to auto-start (delayed)
  7. Opens firewall port if needed (localhost only)
  8. Creates desktop shortcut to `http://localhost:8000`
- `nssm/`: Directory containing NSSM binary (MIT-licensed, redistributable)
- `deploy/dental-notes.env`: Template environment file for per-machine config

**Service configuration:**
```
Service name: DentalNotes
Application: C:\DentalNotes\venv\Scripts\python.exe
Arguments: -m dental_notes.main
Startup: Automatic (Delayed Start)
Recovery: Restart after 5000ms on first failure, 10000ms on second, 30000ms on subsequent
Stdout: C:\DentalNotes\logs\stdout.log
Stderr: C:\DentalNotes\logs\stderr.log
```

**VRAM impact:** None. Service wrapping is OS-level.

### 8. Error Recovery (Watchdog)

**What changes:** The application currently handles errors at the route level (try/except returning error banners) but has no recovery mechanism for:
- GPU crashes (CUDA out of memory, driver crash)
- Microphone disconnects mid-session
- Ollama process dying
- Application hang (deadlock in processing thread)

**Design approach:** Two-layer error recovery:

**Layer 1: In-process health checks** (new `health.py` module)
- GPU health: Attempt `torch.cuda.is_available()` + small tensor allocation
- Mic health: Check if sounddevice stream is active (no errors in callback)
- Ollama health: `OllamaService.is_available()` already exists
- Processing thread health: Check `_processing_thread.is_alive()`
- Expose via `GET /health` endpoint (JSON status of each component)

**Layer 2: External process supervisor** (NSSM auto-restart)
- NSSM detects process exit (crash) and restarts automatically
- For hangs: periodic health check from a lightweight watchdog script that hits `GET /health` and kills the process if it fails N times consecutively

**Existing code affected:**
- `main.py`: Add `/health` endpoint in lifespan or as a route.
- `session/manager.py`: Add try/except in `_processing_loop()` for CUDA errors. On GPU crash: log error, set state to PAUSED (not crash the session), attempt recovery. The session's in-memory transcript chunks are preserved even if transcription temporarily fails.
- `transcription/whisper_service.py`: Add `health_check() -> bool` method that attempts a small transcription. Add recovery method that unloads and reloads the model.
- `audio/capture.py`: Add error callback handling for sounddevice stream errors (device disconnect).

**New file: `watchdog.py`** (external process, not part of FastAPI)
```python
# Lightweight script that runs alongside the main service
# Hits GET /health every 30 seconds
# If 3 consecutive failures: kill and restart the main process
# NSSM runs this as a separate service
```

**Recovery matrix:**

| Failure | Detection | Recovery | Data Impact |
|---------|-----------|----------|-------------|
| CUDA OOM | torch.cuda exception in transcribe() | Unload model, clear CUDA cache, reload | Current chunk lost, session continues |
| Mic disconnect | sounddevice callback error | Pause session, show UI alert, resume on reconnect | No data loss |
| Ollama crash | is_available() returns False | Skip extraction, show "Ollama unavailable" in review | Session saved as RECORDED, extract later |
| Processing thread death | is_alive() check | Restart thread, resume from current state | Current chunk may be lost |
| Full process crash | NSSM detects exit | Restart process | Active session lost, saved sessions preserved (JSON on disk) |

**VRAM impact:** Health check tensor allocation is negligible (<1MB).

### 9. Multi-Machine Deployment

**What changes:** The application runs on a single operatory PC. Multi-machine deployment means installing the same application on 3-5 additional operatory PCs, each running independently (no shared state, no network communication between instances).

**This is simpler than it sounds.** Each machine is a standalone instance. "Multi-machine deployment" is really "repeatable installation" -- the `install.py` script from Feature 7 does the work. The only new concern is per-machine configuration.

**Design approach:**
- `config.py`: Add `machine_id: str = "operatory-1"` for logging/identification.
- `deploy/config-template.env`: Template with machine-specific settings (mic device name, machine_id, Whisper model size based on GPU).
- `install.py`: Accept `--config` flag pointing to a pre-filled .env file for unattended installation.
- Session files are local to each machine (no shared filesystem needed).

**Per-machine configuration differences:**

| Setting | Why It Varies | Example |
|---------|--------------|---------|
| `DENTAL_MACHINE_ID` | Identify which operatory | `operatory-1`, `operatory-2` |
| Mic device name | Different hardware per room | `"Yeti Classic"`, `"Blue Snowball"` |
| `DENTAL_WHISPER_MODEL` | Different GPUs | `small` (GTX 1050), `medium` (GTX 1070 Ti) |
| `DENTAL_COMPUTE_TYPE` | GPU capability | `int8` (CC 6.1), `float16` (CC 7.0+) |
| `DENTAL_OLLAMA_MODEL` | VRAM available | `qwen3:4b` (4GB), `qwen3:8b` (8GB) |

**VRAM impact:** None. Configuration only.

## Recommended Architecture After v2

```
                    NSSM Service Manager
                         |
              +----------+----------+
              |                     |
         dental-notes           watchdog.py
         (FastAPI app)          (health monitor)
              |                     |
              |          GET /health (every 30s)
              |                     |
         FastAPI (main.py)  <-------+
              |
   +----------+----------+-----------+----------+
   |          |          |           |           |
 routes.py  dictation  SSE       hotkey      lifespan
   |          |        stream    listener       |
   |          |          |          |           |
   v          v          v          v           v
SessionStore  WhisperSvc SessionManager    init/shutdown
(JSON+meta)   (shared)   (state machine     (Whisper, Ollama,
   |             |        + auto-pause)      SessionStore,
   |             |            |              HealthChecker)
   |             |     +------+------+
   |             |     |      |      |
   |             |  AudioCap  VAD  Chunker
   |             |  (+error)  |   (+silence
   |             |     |      |    counter)
   |             |     +----->+----->|
   |             |                   |
   |             +<----- transcribe(chunk, hotwords)
   |             |
   |      ClinicalExtractor
   |      (GPU handoff + template selection)
   |             |
   |      +------+------+
   |      |             |
   | ExtractionResult  PatientSummary
   | (SOAP + CDT +     (plain language
   |  3-way speakers)   + next steps)
   |
   +-- appointment_type, batch_date, patient_label, patient_summary
```

## Recommended Project Structure After v2

```
src/dental_notes/
  __init__.py
  main.py                          # FastAPI app + lifespan (M: health endpoint)
  config.py                        # Settings (M: new settings for all features)
  health.py                        # NEW: Component health checker
  watchdog.py                      # NEW: External process monitor (separate entry point)
  audio/
    __init__.py
    capture.py                     # AudioCapture (M: error callback handling)
    vad.py                         # VadDetector (unchanged)
  transcription/
    __init__.py
    whisper_service.py             # WhisperService (M: hotwords, health_check, expanded vocab)
    chunker.py                     # AudioChunker (unchanged)
    stitcher.py                    # deduplicate_overlap (unchanged)
  session/
    __init__.py
    manager.py                     # SessionManager (M: auto-pause, silence counter)
    store.py                       # SessionStore (M: metadata fields)
    speaker.py                     # classify_speaker (M: 3-way classification)
    transcript_writer.py           # TranscriptWriter (unchanged)
  clinical/
    __init__.py
    models.py                      # Pydantic models (M: AppointmentType, PatientSummary, 3-way speaker)
    extractor.py                   # ClinicalExtractor (M: template selection, summary generation)
    prompts.py                     # Base prompts (M: 3-way speaker rules, summary prompt)
    templates.py                   # NEW: Appointment-type prompt overlays
    formatter.py                   # Clipboard formatter (M: include summary option)
    ollama_service.py              # OllamaService (unchanged)
    speaker.py                     # SpeakerReattributor (M: 3-way prompt)
  ui/
    __init__.py
    routes.py                      # HTTP routes (M: batch, auto-pause SSE, type selector, health)
    dictation.py                   # Dictation endpoint (unchanged)
    hotkey.py                      # HotkeyListener (unchanged)
  templates/                       # Jinja2 templates (M: batch dashboard, type selector, summary panel)
  static/                          # CSS/JS (M: batch UI, summary panel styles)
install.py                         # NEW: Windows installer script (project root)
nssm/                              # NEW: NSSM binary for service management
deploy/
  config-template.env              # NEW: Per-machine config template
```

## Data Flow Changes

### v1 Session Lifecycle
```
User clicks Start
  -> SessionManager.start() -> AudioCapture.start() + Whisper.load()
  -> _processing_loop: audio -> VAD -> chunk -> transcribe -> classify_speaker -> write
  -> User clicks Stop
  -> SessionManager.stop() -> flush -> TranscriptWriter.close()
  -> Route creates SavedSession
  -> Route calls extract_with_gpu_handoff()
  -> Redirect to review page
```

### v2 Session Lifecycle (batch + auto-pause + templates + summary)
```
User selects appointment type + clicks Start
  -> SessionManager.start() -> AudioCapture.start() + Whisper.load()
  -> _processing_loop: audio -> VAD -> chunk -> transcribe -> classify_speaker_3way -> write
     + silence counter: if silence > threshold -> auto-pause + SSE event
  -> User clicks "Next Patient" (or Stop)
  -> SessionManager.stop() -> flush -> TranscriptWriter.close()
  -> Route creates SavedSession with appointment_type + batch metadata
  -> If "Next Patient": auto-start new session (same mic, same type or new type selection)
  -> Extraction deferred to review time (batch workflow)
  -> Later: User opens batch dashboard, clicks session to review
  -> Route calls extract_with_gpu_handoff(appointment_type)
     -> Whisper.unload() -> LLM.extract(template_prompt) -> LLM.summarize() -> LLM.unload() -> Whisper.reload()
  -> Review page shows SOAP + patient summary + 3-way speaker labels
```

### Key Data Flow Differences

1. **Extraction is deferred in batch mode.** v1 extracts immediately on stop. v2 batch mode saves the session and starts the next patient. Extraction happens when the dentist reviews sessions at end of day. This avoids the GPU handoff delay between patients.

2. **Summary piggybacks on extraction.** The patient summary is generated in the same GPU handoff window as SOAP extraction, avoiding a second Whisper unload/reload cycle.

3. **Auto-pause is transparent.** The processing loop pauses internally; the UI receives an SSE event. No data flow change -- the loop simply sleeps until resumed.

## Build Order (Suggested Phase Structure)

Features are ordered by: (a) dependency chain, (b) value to clinical workflow, (c) risk/complexity.

### Phase 1: Clinical Intelligence Enhancements
**Features:** Expanded Whisper vocabulary, 3-way speaker classification, appointment templates
**Rationale:** These are the highest clinical value with lowest integration risk. All modify existing code in small, well-bounded ways. No new architectural patterns. Each is independently testable.
**Dependencies:** None (all extend existing components).
**Estimated files modified:** 8 files modified, 1 new file.

Build sub-order within phase:
1. Expanded Whisper vocabulary (smallest change, immediate accuracy improvement)
2. 3-way speaker classification (extend existing pattern, no new deps)
3. Appointment templates (new file + prompt refactoring)

### Phase 2: Workflow and Recovery
**Features:** Batch session management, auto-pause/resume, error recovery watchdog
**Rationale:** Batch workflow is the second-highest value feature (end-of-day note completion). Auto-pause supports batch (hands-free between patients). Error recovery ensures reliability for all-day operation.
**Dependencies:** Phase 1 (templates feed into batch workflow -- session needs appointment_type).
**Estimated files modified:** 6 files modified, 3 new files.

Build sub-order within phase:
1. Auto-pause (small change in processing loop, enables batch flow)
2. Batch session management (UI + route changes, uses auto-pause)
3. Error recovery / health checks (independent but needed before production)

### Phase 3: Patient Summary
**Feature:** Patient summary generation (REV-04)
**Rationale:** Separate phase because it requires a second LLM call within GPU handoff and changes the extraction pipeline sequence. Lower priority than workflow features.
**Dependencies:** Phase 1 (appointment templates influence summary content).
**Estimated files modified:** 5 files modified, 0-1 new files.

### Phase 4: Deployment Infrastructure
**Features:** Windows installer, auto-start on boot, multi-machine config
**Rationale:** Last because it wraps the application without changing it. All clinical features should be stable before packaging for deployment.
**Dependencies:** Phase 2 (error recovery / NSSM service are co-designed).
**Estimated files modified:** 2 files modified, 4+ new files.

Build sub-order within phase:
1. Multi-machine config (config.py changes, template files)
2. Windows installer script (install.py)
3. NSSM service configuration + auto-start

## Anti-Patterns to Avoid

### Anti-Pattern 1: Audio-Based Speaker Diarization on Constrained GPU

**What people do:** Add pyannote or another neural diarization model to identify speakers by voice.
**Why it is wrong for this project:** Pyannote 4.x uses 6-9GB VRAM. Even pyannote 3.1 uses ~1.6GB and cannot coexist with Whisper on 4-8GB GPUs. The sequential GPU handoff pattern (Whisper -> LLM) does not extend to three models. Adding audio diarization would require either: (a) CPU-only pyannote (adds minutes of processing time per session), or (b) a third GPU handoff step (Whisper unload -> pyannote -> pyannote unload -> Whisper reload -> ... -> LLM), which is unacceptably slow and fragile.
**Do this instead:** Keep the text-based keyword classification (CPU, zero VRAM) + LLM reattribution (runs in existing Ollama call). Extend keyword patterns for Assistant role. The dental context provides strong textual signals -- doctors use clinical terms, patients report symptoms, assistants relay instruments and confirm readiness.

### Anti-Pattern 2: Bundling CUDA into PyInstaller

**What people do:** Use PyInstaller to create a single .exe with all CUDA DLLs bundled.
**Why it is wrong for this project:** Adds 400-800MB to installer size. Creates CUDA version conflicts with system drivers. Makes GPU debugging impossible (users cannot check CUDA version, run nvidia-smi against bundled runtime). Target machines already have CUDA installed and working (they run Dentrix + GPU-accelerated workflows).
**Do this instead:** Use NSSM to wrap the existing Python + pip installation as a Windows service. The install script checks for prerequisites and configures the service. Much simpler, much more debuggable.

### Anti-Pattern 3: Combining SOAP Extraction and Patient Summary in One Prompt

**What people do:** Ask the LLM to produce both the clinical SOAP note and the patient summary in a single call to save time.
**Why it is wrong:** The SOAP note requires medical precision and jargon. The patient summary requires 8th-grade reading level and zero jargon. These are contradictory writing styles. Combining them degrades both outputs -- the LLM compromises between clinical precision and lay accessibility.
**Do this instead:** Two sequential LLM calls within the same GPU handoff window. First call: SOAP extraction (existing prompt). Second call: summary generation from the SOAP output (new prompt focused on plain language). The ~10-15 second overhead is negligible compared to the quality improvement.

### Anti-Pattern 4: Shared State Between Operatory Machines

**What people do:** Set up a shared network drive or database so all operatory PCs share session data.
**Why it is wrong for this project:** Patient audio transcripts must not traverse the network (HIPAA). Adding network dependencies creates failure modes (network down = all machines down). The dentist reviews notes on the machine where they were recorded. There is no use case for cross-machine session access.
**Do this instead:** Each machine is a standalone instance with local storage. Multi-machine deployment means "run the same installer N times with different .env configs."

### Anti-Pattern 5: Auto-Resume on Sound Detection

**What people do:** When auto-paused, try to auto-resume by continuously monitoring the mic for speech.
**Why it is wrong:** During pause, the mic stream is stopped (saves CPU/power). To detect speech, you would need to keep the stream running and the VAD processing -- defeating the purpose of pausing. Additionally, any ambient noise (hallway conversation, equipment) could trigger false resume.
**Do this instead:** Auto-pause is one-directional. Resume requires explicit user action (UI button or F8 hotkey). This matches the clinical workflow: the dentist calls the next patient, seats them, gets ready, then explicitly starts/resumes recording.

## Integration Points

### Internal Boundaries

| Boundary | Communication | v2 Changes |
|----------|---------------|------------|
| SessionManager <-> AudioCapture | Direct method calls, thread-safe queue | Add error callback for device disconnect |
| SessionManager <-> WhisperService | Direct method calls in processing thread | Add hotwords parameter passthrough |
| SessionManager <-> UI (routes) | app.state reference, SSE events | Add auto-pause SSE event type |
| ClinicalExtractor <-> OllamaService | Direct method calls | Add summary generation call |
| ClinicalExtractor <-> WhisperService | GPU handoff (unload/reload) | Extended handoff window for summary |
| SessionStore <-> filesystem | JSON read/write | Additional metadata fields |
| Watchdog <-> FastAPI | HTTP health endpoint | New /health route |
| NSSM <-> Python process | Process lifecycle management | New deployment artifact |

### External Services

| Service | Integration Pattern | v2 Notes |
|---------|---------------------|----------|
| Ollama (localhost:11434) | HTTP via ollama Python client | Unchanged; health check added |
| sounddevice (PortAudio) | C library via Python bindings | Error callback for device loss |
| NSSM | OS service manager | New; wraps Python process |

## VRAM Budget (8GB Target GPU)

| Component | VRAM Usage | When Loaded | v2 Change |
|-----------|------------|-------------|-----------|
| Whisper small (int8) | ~1GB | During recording | Unchanged |
| silero-vad | ~50MB (CPU) | During recording | Unchanged (CPU only) |
| Qwen3 8B (Q4) | ~5GB | During extraction | Unchanged |
| Qwen3 4B (Q4) | ~3GB | Fallback on 4GB GPU | Unchanged |
| Patient summary | 0 (reuses loaded Qwen3) | After SOAP extraction | NEW -- no additional VRAM |
| 3-way speaker | 0 (reuses loaded Qwen3) | During reattribution | Unchanged |
| Appointment templates | 0 (text in prompt) | During extraction | Unchanged |
| **Peak during recording** | **~1.05GB** | | **No change** |
| **Peak during extraction** | **~5GB (8B) or ~3GB (4B)** | | **No change** |

The v2 features add zero VRAM pressure. All new functionality is either CPU-based (text classification, auto-pause logic, health checks) or reuses the existing Ollama session (summary, templates).

## Sources

- [pyannote VRAM issue #1963](https://github.com/pyannote/pyannote-audio/issues/1963) -- pyannote 4.0.3 uses 6x more VRAM (9.54GB vs 1.59GB)
- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) -- model card with requirements
- [CPU-only diarization alternative](https://medium.com/@shashwat.gpt/towards-approximate-fast-diarization-a-cpu-only-alternative-to-pyannote-3-1-2ba4843db297) -- CPU approach feasibility
- [NSSM - Non-Sucking Service Manager](https://nssm.cc/) -- Windows service wrapper
- [Metallapan: Windows service with pywin32 + PyInstaller](https://metallapan.se/post/windows-service-pywin32-pyinstaller/) -- alternative approach (rejected)
- [Whisper4Windows BUILD.md](https://github.com/BaderJabri/Whisper4Windows/blob/main/BUILD.md) -- CUDA bundling challenges
- [faster-whisper hotwords](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py) -- hotwords parameter in transcribe()
- [Whisper prompting guide](https://developers.openai.com/cookbook/examples/whisper_prompting_guide) -- initial_prompt best practices
- [LLM-based speaker diarization correction](https://www.sciencedirect.com/science/article/abs/pii/S0167639325000391) -- text-based speaker correction research
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) -- structured output capabilities

---
*Architecture research for: Dental Notes v2.0 feature integration*
*Researched: 2026-03-28*
