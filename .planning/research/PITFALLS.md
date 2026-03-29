# Pitfalls Research: v2.0 Feature Addition

**Domain:** Adding production features (installer, auto-start, error recovery, batch workflow, auto-pause, speaker diarization, templates, patient summaries) to a working local-first dental clinical tool
**Researched:** 2026-03-28
**Confidence:** HIGH (v1 codebase analyzed, GPU constraints verified, Windows platform issues confirmed via official docs)

## Critical Pitfalls

### Pitfall 1: Windows Service Session 0 Isolation Kills Audio Access

**What goes wrong:**
Windows services run in Session 0, which is completely isolated from the interactive desktop session where audio devices live. A dental-notes process running as a Windows service via NSSM or pywin32 cannot access the microphone at all. The service starts, the server runs, but `sounddevice.InputStream` fails silently or throws a PortAudio error because Session 0 has no audio device access. This is not a permissions issue that can be fixed with a config change -- it is an architectural constraint of Windows since Vista.

**Why it happens:**
The obvious approach to "auto-start on boot" is to install as a Windows service. Services survive logoff, restart automatically, and are the standard pattern for server processes. But Windows explicitly isolates services from interactive hardware (display, audio, USB HID) as a security measure. The dental-notes server needs PortAudio/sounddevice access to the microphone, which only exists in the user's interactive desktop session.

**How to avoid:**
- Use Windows Task Scheduler with an "At logon" trigger instead of a Windows service. This runs the process in the user's interactive session where audio devices are accessible.
- Alternatively, place a shortcut in the Startup folder (`shell:startup`) or use a registry Run key (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
- NSSM is the wrong tool here. Do not use it. Task Scheduler gives restart-on-failure, delayed start, and "run whether user is logged in or not" (though that last option re-introduces Session 0 issues -- use "run only when user is logged on").
- The installer should create a Task Scheduler entry, not a Windows service.

**Warning signs:**
- Audio device enumeration returns empty list but worked in development
- `sounddevice.PortAudioError` or similar at startup in service mode
- Server starts fine via command line but fails when launched as a service
- NSSM shows the service as "running" but the web UI shows no microphone options

**Phase to address:** Windows Installer / Auto-Start phase. This is a design-time decision, not a fix-later issue. Choose Task Scheduler from the start.

---

### Pitfall 2: Breaking the Working v1 Pipeline While Adding Features

**What goes wrong:**
v1 works end-to-end: record, transcribe, extract SOAP notes, review, copy, finalize. 249 tests pass. Adding batch workflow, auto-pause, speaker diarization, and appointment templates all touch SessionManager -- the central orchestrator. A refactor to support batch workflow changes the state machine (IDLE -> RECORDING -> PAUSED -> IDLE becomes more complex with BATCH_IDLE, AUTO_PAUSED, etc.). This breaks the existing start/pause/resume/stop contract that the UI routes depend on. The clinical extractor's GPU handoff sequence (Whisper unload -> LLM -> LLM unload -> Whisper reload) has to work with the new batch flow. One wrong state transition and the entire pipeline breaks.

This is exactly how v0 died -- overengineering killed a working system. v1 explicitly avoided this. v2 must not repeat it.

**Why it happens:**
- The SessionManager state machine is tightly coupled to the single-session workflow. Adding batch and auto-pause requires new states but the existing routes/tests assume the v1 state set.
- Developers modify shared code (manager.py, routes.py) for new features and inadvertently change behavior that v1 depends on.
- New features are developed in-place rather than behind feature flags or as additive extensions.
- The 249 existing tests provide a safety net, but only if they are kept passing. If the temptation is "I'll fix the tests later," they stop being a safety net.

**How to avoid:**
- **Make all v2 features additive, not substitutive.** The existing SessionManager.start/pause/resume/stop must continue to work exactly as they do today. Batch workflow is a layer on top, not a replacement.
- **Introduce a BatchManager that wraps SessionManager.** BatchManager owns the queue of sessions and calls SessionManager.start() / stop() for each one. SessionManager does not know about batches.
- **Run the full 249-test suite after every change.** Zero regressions tolerated. If a refactor breaks existing tests, the refactor is wrong.
- **Add v2 features behind configuration.** New behavior is opt-in. The default behavior is v1.
- **Apply the same Pragmatic TDD discipline from v1:** test file first, integration tests mandatory, human verification gates are blocking.

**Warning signs:**
- Existing tests start failing during v2 development
- SessionManager state machine gets more than 6 states
- Routes.py modifications change the behavior of existing endpoints
- "Temporary" test skips or `@pytest.mark.skip` appear on v1 tests
- The phrase "we need to refactor the core first" appears

**Phase to address:** Every v2 phase. This is a meta-pitfall that applies throughout. The first v2 plan should include "all 249 tests still pass" as a gate.

---

### Pitfall 3: Speaker Diarization VRAM Explosion on 4-8 GB GPUs

**What goes wrong:**
3-way speaker identification (doctor/patient/assistant) seems to require a speaker diarization model. pyannote-audio v3.x uses ~1.6 GB VRAM, but v4.0.3 uses 6x more (~9.5 GB peak) due to a memory spike during reconstruction. This exceeds the GTX 1070 Ti (8 GB) entirely and is completely impossible on GTX 1050 (4 GB). Even pyannote v3.x at 1.6 GB cannot coexist with Whisper (~1.5 GB int8) -- together they exceed the GTX 1050. And the GPU handoff pattern (unload one model, load another) would mean three sequential model loads per session: Whisper, diarization model, LLM. Each handoff adds 10-30 seconds of model loading time.

**Why it happens:**
- Speaker diarization is a separate ML model with its own VRAM footprint. It cannot share VRAM with Whisper or the LLM.
- pyannote is the most commonly recommended solution, but its VRAM usage has increased dramatically in recent versions.
- Developers assume "small model = small VRAM" without benchmarking on target hardware.
- WhisperX bundles diarization with transcription but still loads pyannote under the hood, inheriting the same VRAM problem.

**How to avoid:**
- **Keep the existing text-based speaker classification as the primary approach.** The v1 keyword-based classifier in `session/speaker.py` plus the LLM-based SpeakerReattributor in `clinical/speaker.py` already provides Doctor/Patient classification with zero additional VRAM. Extend this approach to 3-way classification.
- **Add "Assistant" patterns to the text-based classifier.** Assistant speech patterns are distinct: "suction," "open wider," "rinse," "I'll get that," instrument names, confirmations of doctor instructions. This is a pattern-matching problem, not a model problem.
- **Enhance the LLM SpeakerReattributor to handle 3 speakers.** The Qwen3 8B model already runs during the extraction phase. Adding a 3-speaker prompt is a prompt change, not a model change. Zero additional VRAM.
- **If audio-based diarization is truly needed later**, evaluate Picovoice Falcon (CPU-only, 100x more efficient than pyannote, no GPU required). But it requires an API key and has a 250 min/month free tier limit. Evaluate this only after text-based 3-way classification proves insufficient.
- **Do not use pyannote v4.x.** Even v3.x is risky on 4-8 GB VRAM.

**Warning signs:**
- CUDA OOM errors when loading a diarization model alongside Whisper
- Model loading times exceed 30 seconds for a single feature
- The GPU handoff chain grows to 3+ sequential model swaps
- A new pip dependency pulls in 2+ GB of model weights

**Phase to address:** Speaker Identification phase. The critical decision is text-based vs. model-based, and it must be made before any implementation starts. Text-based is the right default for these VRAM constraints.

---

### Pitfall 4: Auto-Pause Silence Detection Triggers During Dental Procedures

**What goes wrong:**
Auto-pause is meant to detect silence between patients and automatically segment sessions. But dental appointments have extended silences during procedures -- patient has mouth open (cannot speak), dentist is concentrating on a procedure, only the drill/suction sound. A silence detector tuned for "between patients" (minutes of silence) will work, but one tuned for "pause in conversation" (10-30 seconds) will fire constantly during procedures, fragmenting a single appointment into dozens of tiny sessions.

The reverse is also dangerous: between patients, there is often background chatter (staff conversations, phone calls, hallway noise) that is not silence. A naive silence detector would fail to trigger, concatenating two patients' appointments into one session.

**Why it happens:**
- "Silence" in a dental operatory is not acoustic silence -- it is the absence of patient-directed clinical speech, but with 70-90 dB of equipment noise, staff chatter, and ambient sound.
- Developers test in quiet environments (home office) where silence is actually silent.
- The silence gap threshold that works for within-session pause detection (1.5 seconds, currently used by AudioChunker) is completely wrong for between-patient detection (needs to be 2-5 minutes).
- No single threshold works for both short pauses (within an appointment) and long gaps (between appointments).

**How to avoid:**
- **Separate within-session pause detection from between-session gap detection.** These are different problems with different thresholds.
- **Use a multi-signal approach for between-patient detection:** extended silence (2+ minutes) + optional manual confirmation + possible ambient audio level change (equipment off).
- **Default to manual session boundaries with auto-pause as an assist, not the primary mechanism.** "Did you mean to start a new session?" prompt after detecting a long gap, rather than automatic session splitting.
- **Start with a conservative threshold (5 minutes of near-silence) and let the dentist tune it down.** False negatives (missed split) are far less harmful than false positives (fragmented appointment).
- **Consider a hybrid approach:** manual "Next Patient" button is the primary mechanism, with auto-pause as a safety net that kicks in only after very long silence (prevents recording 2 hours of empty room if the dentist forgets to stop).

**Warning signs:**
- A single appointment gets split into multiple sessions
- Two patients' conversations end up in one session
- The dentist has to manually merge or re-split sessions frequently
- Auto-pause fires during a routine procedure when patient's mouth is open
- Between-patient gap is not detected because staff are chatting nearby

**Phase to address:** Batch Workflow / Auto-Pause phase. Build manual "Next Patient" first, add auto-pause as an optional enhancement second.

---

### Pitfall 5: Windows Installer Packaging CUDA/CTranslate2 DLL Hell

**What goes wrong:**
Packaging a Python application that depends on faster-whisper (CTranslate2), PyTorch (for silero-vad), CUDA, cuDNN, and sounddevice into a Windows installer is an order-of-magnitude harder than packaging a normal Python app. PyInstaller struggles with CUDA: CTranslate2's native libraries are not auto-discovered as hidden imports, CUDA DLLs (cublas64_*.dll, cudnn*.dll) must be explicitly included, and the resulting bundle is 3-5 GB. Version mismatches between ctranslate2, CUDA toolkit, and cuDNN cause silent failures or crashes that only manifest on machines with different GPU driver versions. Furthermore, CUDA sticky errors (OOM, driver crash) corrupt the CUDA context and cannot be recovered within the same process -- the Python process must be restarted entirely.

**Why it happens:**
- Python ML packaging is notoriously fragile. Each library (faster-whisper, torch, sounddevice) has its own native extension loading mechanism.
- ctranslate2 >=4.5.0 requires CUDA 12 + cuDNN 9. ctranslate2 3.24.0 requires CUDA 11 + cuDNN 8. The office machines may have different CUDA toolkit versions installed.
- PyInstaller's auto-detection does not find ctranslate2's shared libraries, PortAudio's DLL, or CUDA runtime libraries.
- The bundled installer includes torch (2+ GB alone), making distribution impractical over slow office internet.

**How to avoid:**
- **Do not use PyInstaller.** Use an embedded Python distribution (WinPython or python.org embeddable zip) + pip install + Inno Setup for the installer wrapper. This avoids DLL discovery problems entirely because the packages install normally.
- **Ship a `requirements.txt` with pinned versions** including the exact ctranslate2 version that matches the CUDA version on target machines.
- **Detect CUDA version at install time** (check nvidia-smi output) and install the matching ctranslate2 wheel. The Inno Setup installer can run a Python script that checks GPU compatibility.
- **Pre-download Whisper model files during installation** rather than on first run. First-run model downloads over slow office internet cause confusing "it's not working" complaints.
- **Expect the installer to be 1-2 GB.** This is unavoidable with CUDA ML dependencies. Use offline installer (no internet required during install).
- **Separate the Ollama installation from the dental-notes installer.** Ollama has its own installer and should be a prerequisite, not bundled. The dental-notes installer checks for Ollama and prompts to install if missing.

**Warning signs:**
- PyInstaller bundle exceeds 5 GB
- `ImportError: DLL load failed` errors on target machines that worked on dev machine
- ctranslate2 loads but `device="cuda"` fails despite nvidia-smi showing the GPU
- Different behavior between `python start_server.py` and the packaged executable
- Users report "it worked yesterday" after a Windows Update changes CUDA driver version

**Phase to address:** Windows Installer phase. The packaging approach (embedded Python vs. PyInstaller) is a design decision that must be made before implementation.

---

### Pitfall 6: GPU Crash Recovery Requires Process Restart -- Not Just Exception Handling

**What goes wrong:**
When a CUDA operation fails with an out-of-memory error or driver crash, the CUDA context becomes corrupted. This is called a "sticky error" in CUDA terminology. After a sticky error, ALL subsequent CUDA API calls return the same error. `torch.cuda.empty_cache()` does not fix it. `del model` does not fix it. The Python process's entire CUDA state is poisoned. The only recovery is to terminate and restart the Python process. But the current dental-notes architecture runs as a single long-lived `uvicorn` process. A CUDA crash during extraction kills not just extraction but also the recording pipeline (Whisper), and the process must be restarted manually.

**Why it happens:**
- The v1 GPU handoff pattern (`extract_with_gpu_handoff`) wraps extraction in try/finally and reloads Whisper. This handles normal errors but not CUDA context corruption.
- Developers test error recovery by catching Python exceptions, not by simulating actual GPU driver failures.
- The `OllamaService.unload()` method catches exceptions silently (`logger.warning`) -- if the Ollama server itself has crashed, this masks the problem.
- The single-process architecture means one GPU failure takes down everything.

**How to avoid:**
- **Implement a watchdog/supervisor pattern.** The dental-notes server process should be launched by a lightweight parent process (or Task Scheduler with restart-on-failure). When the server crashes or becomes unresponsive, the supervisor restarts it automatically.
- **Add a health-check endpoint** (`/health`) that verifies CUDA availability, Ollama reachability, and microphone access. The supervisor pings this endpoint and restarts if unhealthy.
- **Move LLM extraction to a subprocess.** Instead of running `extractor.extract()` in the same process that owns the audio pipeline, spawn a short-lived subprocess for extraction. If extraction crashes, only the subprocess dies. The main process (audio/Whisper) is unaffected.
- **NSSM's auto-restart works here for the supervisor** (since the supervisor is just a process launcher, not an audio consumer). Only the child uvicorn process needs interactive session access.
- **Catch `RuntimeError: CUDA error` specifically** and trigger a graceful self-restart rather than continuing with a poisoned CUDA context.
- **For microphone disconnection:** sounddevice does not detect USB hot-unplug. Poll `sounddevice.query_devices()` periodically -- but note that on Windows, `query_devices()` does not update after startup without reinitializing PortAudio. The `python-sounddevice-hotplug` fork addresses this, but it is a non-standard dependency. The pragmatic approach: if the audio stream callback stops receiving data, surface an error in the UI and prompt the user to reconnect and restart the session.

**Warning signs:**
- CUDA errors persist across multiple extraction attempts without a process restart
- `torch.cuda.is_available()` returns False after an OOM error (poisoned context)
- The server "hangs" with no response after a GPU error, requiring manual kill
- Ollama becomes unresponsive but the server does not report it
- A USB microphone disconnect causes an unrecoverable crash

**Phase to address:** Error Recovery phase. The subprocess extraction pattern and supervisor/watchdog should be designed early, as they affect the process architecture.

---

### Pitfall 7: Appointment Templates Become a Maintenance Nightmare

**What goes wrong:**
Different appointment types (exam, restorative, hygiene, endo, extraction) need different SOAP note structures. The temptation is to create a separate extraction prompt, Pydantic model, and formatter for each template type. With 5+ templates, each with their own prompt/model/formatter, any change to the base extraction logic must be replicated across all templates. A bug fix in the exam template prompt does not propagate to the endo template. The template system becomes the most fragile part of the codebase.

**Why it happens:**
- Each appointment type has legitimately different documentation requirements (an extraction note needs different Objective fields than a hygiene note).
- Copy-paste is the easy way to create a new template: duplicate the exam prompt, modify for endo. Now you have two independent prompts to maintain.
- The Pydantic model for `SoapNote` is currently one model. Splitting into `ExamSoapNote`, `RestoSoapNote`, `EndoSoapNote` creates a type explosion.

**How to avoid:**
- **Use a single SoapNote model with optional fields**, not separate models per template. The current `SoapNote` already has optional fields (medications, va_narrative). Add more optionals for template-specific sections (procedure_details, perio_charting, endo_specifics).
- **Use a single base extraction prompt with template-specific addenda.** The system prompt is the same for all templates. A template-specific section at the end says "For this [exam/restorative/endo] appointment, also include [specific fields]." This is append-only, not a full duplicate.
- **Templates control what sections are shown in the review UI, not what the LLM generates.** The LLM always generates the full SoapNote. The template determines which sections are displayed prominently and which are collapsed or hidden.
- **Store template definitions as data (JSON/dict), not as code.** A template is: `{ "name": "Restorative", "required_sections": ["procedure_details", "materials"], "prompt_addendum": "..." }`.
- **Limit to 5 templates initially:** Exam, Restorative, Hygiene, Endo, Extraction. Do not build a template editor. Do not support custom templates in v2.

**Warning signs:**
- More than one extraction prompt file exists with duplicated content
- A bug fix requires changes in multiple template-specific files
- The Pydantic model hierarchy has more than 2 levels of inheritance
- Adding a new template type requires more than 15 minutes
- Template selection changes the LLM model or extraction pipeline, not just the prompt

**Phase to address:** Appointment Templates phase. The "single model, template addendum" architecture must be decided before implementation.

---

### Pitfall 8: Batch Workflow State Corruption Loses Patient Notes

**What goes wrong:**
Batch workflow means recording multiple patients and completing notes at end of day. The dentist records Patient A, stops, records Patient B, stops, records Patient C, stops. At end of day, they review and complete all three notes. If any step in this chain corrupts the session store -- a power failure during atomic write, a JSON serialization error on one session that prevents loading the session list, or a finalize on the wrong session ID -- patient data is lost. The current `SessionStore` uses individual JSON files with atomic writes (tempfile + os.replace), which is good. But batch workflow adds new failure modes: what if the dentist accidentally finalizes (deletes) Session A thinking it was Session B? What if the server crashes mid-extraction and the session is stuck in RECORDED status forever?

**Why it happens:**
- v1 was designed for one session at a time. The session list exists but was a late addition.
- JSON files on disk are not a database -- there is no ACID guarantee across multiple files.
- Session IDs are UUIDs with no human-readable identifier. In a list of 5-10 sessions, the dentist relies on timestamps and transcript previews to identify which is which.
- Finalize is destructive (deletes transcript file and session JSON). There is no undo.

**How to avoid:**
- **Add a patient identifier (or appointment label) to each session.** Not a full patient name (HIPAA), but something like "9:00 AM - Exam" or "Patient 3 - Restorative" that the dentist enters at session start or after recording. This prevents wrong-session finalization.
- **Add a "soft delete" step before hard delete.** Finalize moves the session to a "finalized" state but keeps the JSON for 24 hours. A separate cleanup job purges finalized sessions older than 24 hours. This gives the dentist a recovery window.
- **Show a confirmation dialog with session details before finalization.** "You are about to permanently delete the transcript for [9:00 AM Exam, 15 minutes, 3 pages]. Are you sure?"
- **Implement auto-save of extraction results.** If the server crashes during extraction, the session should be in RECORDED state (not lost) and extraction can be retried. The current code already does this correctly.
- **Back up session JSON before finalization.** Write to a `finalized/` directory with a timestamp. Purge after 7 days. This is the "oh no" recovery path.
- **Test the failure modes:** kill the server during extraction, corrupt a session JSON file, finalize twice. The system must handle all of these gracefully.

**Warning signs:**
- Sessions disappear from the list unexpectedly
- The dentist finalizes the wrong session because they all look the same
- A crashed extraction leaves a session in a state where it cannot be re-extracted
- The `sessions/` directory accumulates hundreds of stale JSON files
- Power failure during a write creates a 0-byte JSON file that crashes the list endpoint

**Phase to address:** Batch Workflow phase. Session labeling and soft-delete should be implemented before batch workflow is tested with real patients.

---

### Pitfall 9: Multi-Machine Deployment Without Centralized Configuration

**What goes wrong:**
v2 targets deployment across multiple operatory PCs. Each machine needs dental-notes installed with the correct CUDA version, Ollama model, microphone device, and server settings. Without a deployment strategy, each machine becomes a snowflake: different Python versions, different ctranslate2 versions, different settings. When a bug is fixed, it must be manually deployed to every machine. When a prompt is updated, every machine's prompt file must be updated. With 3-5 operatory PCs, manual management is tedious but possible. At 10+, it is unsustainable.

**Why it happens:**
- v1 was single-machine. There was no deployment story.
- Each operatory PC may have different GPU hardware (mix of GTX 1050 and 1070 Ti).
- Microphone devices differ per machine (different USB ports, different device names).
- Settings are in `config.py` with environment variable overrides (`DENTAL_*`), but there is no mechanism to push config changes to all machines.

**How to avoid:**
- **Create a machine-specific config file** (`dental-notes.env` or `dental-notes.toml`) that the installer generates during setup. This file captures machine-specific settings: GPU model, CUDA version, microphone device, Whisper model size.
- **Separate machine-specific config from shared config.** Shared config (prompts, templates, extraction settings) should be in a single location that all machines read from -- either a shared network drive path or pulled from a local git repo.
- **The installer should auto-detect and configure:** GPU model + CUDA version -> ctranslate2 version + Whisper model size; available microphones -> default device selection; Ollama availability -> install prompt if missing.
- **Version the installation.** Each machine should report its dental-notes version. A simple `/version` endpoint returns the version string. This makes it easy to verify all machines are on the same version.
- **Do not build a fleet management system.** For 3-5 machines, a USB drive with the installer + a one-page setup checklist is adequate. Over-engineering deployment for a single dental practice is a v0-style mistake.
- **Document the "add a new machine" process** as a 10-step checklist, not an automated pipeline.

**Warning signs:**
- Two machines produce different SOAP notes from the same transcript (different model or prompt versions)
- A bug fix is deployed to one machine but not the others
- A machine update (Windows Update, CUDA driver update) breaks dental-notes on one PC but not others
- No one knows which version is running on which machine
- The deployment process requires a developer (not office staff)

**Phase to address:** Multi-Machine Deployment phase. But the groundwork (externalized config, version endpoint) should be laid in the Installer phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Bundling everything with PyInstaller | Single .exe distribution | 5+ GB bundle, CUDA DLL hell, version mismatch nightmares, impossible to debug | Never for CUDA ML apps. Use embedded Python + Inno Setup |
| Running LLM extraction in-process | Simpler code, no IPC needed | GPU crash takes down the entire server (audio + web UI) | v2 prototype only. Move to subprocess before production deployment |
| Copy-pasting extraction prompts per template | Quick to create new template | Divergent prompts, bug fixes not propagated, maintenance burden | Never. Use single base prompt + template addenda |
| Hardcoding silence thresholds for auto-pause | Quick to implement | Breaks in different operatory environments (noise levels vary) | v2 MVP only with documented plan to make configurable |
| Using sounddevice for hot-plug detection | Standard library, no extra deps | Does not detect USB disconnect on Windows after initialization | Acceptable if UI shows "microphone may be disconnected" based on data flow, not device enumeration |
| Skipping session labeling in batch mode | Faster to ship batch workflow | Wrong-session finalization risk, all sessions look identical | Only if session count is reliably < 3/day. Not acceptable at scale |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Windows Task Scheduler (auto-start) | Creating a Windows service via NSSM | Task Scheduler with "At logon" trigger -- services cannot access audio devices (Session 0 isolation) |
| Inno Setup installer | Bundling CUDA runtime in the installer | Detect CUDA version at install time, install matching ctranslate2 wheel. Require NVIDIA driver as prerequisite |
| Ollama (multi-machine) | Assuming Ollama is installed on every target PC | Installer checks for Ollama, prompts to install if missing, verifies model is pulled |
| sounddevice (mic disconnect) | Using `query_devices()` to detect hot-unplug | `query_devices()` does not update on Windows after init. Monitor audio callback data flow instead -- if no blocks arrive for N seconds, surface an error |
| SessionStore (batch workflow) | Assuming JSON file operations are atomic on Windows | Already using tempfile + os.replace which IS atomic. But directory listing (glob) is not -- a concurrent write during list can return partial data. Use file locking or accept eventual consistency |
| GPU handoff (new models) | Adding diarization model to the handoff chain | Do not add a third model. Keep text-based speaker classification. The handoff chain (Whisper -> LLM -> Whisper) is already the right length |
| Whisper vocabulary (expanded) | Concatenating a massive initial_prompt | Whisper `initial_prompt` has a 224-token limit after tokenization. The existing prompt is already near capacity. Additional terms must replace less important ones, not be appended |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Three-model GPU handoff chain (Whisper -> diarization -> LLM) | 30-60 second model loading between each swap, 90+ second total processing per session | Eliminate diarization model. Use text-based speaker classification. Keep two-model handoff | Immediately on 4GB VRAM, painfully slow even on 8GB |
| Auto-pause polling at high frequency | CPU usage spikes, audio queue backup, processing thread starvation | Poll silence state at 1-2 second intervals, not every audio block | At any scale -- polling every 100ms for silence is wasteful |
| Session JSON files accumulating on disk | Slow session list loading, disk space consumption | Auto-cleanup finalized sessions after 24h. Cap stored sessions at 50 | After ~100 sessions (weeks of use without cleanup) |
| LLM extraction running on main uvicorn process | asyncio event loop blocked during 30-60 second extraction, web UI unresponsive | Already using `run_in_executor` which is correct. But move to subprocess for crash isolation | Already mitigated for blocking; subprocess needed for crash recovery |
| Whisper model re-download on every machine install | 500MB+ download per machine, slow office internet | Pre-download model during installer setup, bundle model file in installer or shared network path | First install on every machine |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Installer runs with admin privileges and stores config with admin-only ACLs | Standard user cannot start the server after reboot | Install to user-writable location (`%LOCALAPPDATA%\DentalNotes\`), run as standard user |
| Session labels contain patient names | Patient identifiers on disk in cleartext, HIPAA exposure | Session labels should be time-based ("9:00 AM Exam") or sequential ("Patient 3"), never patient names |
| Patient summary (plain-language) printed or shared without consent | HIPAA violation if summary leaves the office | Patient summary is screen-only, never auto-printed. Copy button requires explicit click |
| Error recovery logs include transcript content for debugging | PHI in log files, accessible to anyone with machine access | Sanitize all log messages. Log session IDs, error types, and stack traces -- never transcript content |
| Multi-machine deployment uses shared network credentials | One compromised machine exposes all | Each machine has independent local installs. No shared credentials. No network-shared patient data |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Auto-pause fires during a procedure without clear indication | Dentist does not know recording paused, misses critical documentation | Visible, unmistakable "PAUSED" indicator on screen. Audio chime on auto-pause. Easy one-tap resume |
| Batch session list shows only timestamps | Dentist cannot tell which session is which patient | Show session label + transcript preview (first sentence) + duration + status badge |
| Template selection is required before recording starts | Adds friction to starting a session. Dentist may not know procedure type until mid-appointment | Default template (General Exam). Allow changing template before or after recording. Template affects note generation, not recording |
| "Next Patient" button ends recording without confirmation | Accidental tap loses the recording boundary | Confirmation: "End current session and start next patient?" with Cancel option |
| Patient summary uses medical jargon the patient cannot understand | Defeats the purpose of a plain-language summary | Explicitly instruct LLM to use 8th-grade reading level. No abbreviations, no CDT codes, no Latin terms |
| Windows installer requires reboot | Disrupts the dental practice workflow | Design for no-reboot installation. Only NVIDIA driver updates require reboot, and those are a prerequisite |

## "Looks Done But Isn't" Checklist

- [ ] **Auto-start:** Server starts after user logon -- verify it works after a clean reboot (not just after manual login)
- [ ] **Auto-start:** Server survives a user logoff + logon cycle (Task Scheduler re-triggers correctly)
- [ ] **Installer:** Works on a clean Windows 10 machine with no Python installed -- verify on a fresh VM, not the dev machine
- [ ] **Installer:** Correct CUDA version detected and matching ctranslate2 installed -- verify on both GTX 1050 (CUDA 11) and GTX 1070 Ti (CUDA 12) if they differ
- [ ] **Batch workflow:** 5 sessions recorded and all 5 appear in session list with correct previews -- verify after server restart (persistence works)
- [ ] **Auto-pause:** Does NOT trigger during a 5-minute dental procedure silence -- verify with real appointment (not just quiet room)
- [ ] **Auto-pause:** DOES trigger after 5 minutes of genuine between-patient silence -- verify the threshold actually works
- [ ] **Speaker ID (3-way):** "Suction please" and "Bite down" correctly attributed to Doctor/Assistant -- verify against 10+ real utterances
- [ ] **Templates:** Changing template after recording does not lose the recording -- verify the template only affects extraction, not the stored transcript
- [ ] **Error recovery:** Kill the server process during extraction -- verify the session is still recoverable after restart
- [ ] **Error recovery:** Unplug the USB microphone during recording -- verify the UI shows an error and the partial transcript is saved
- [ ] **Multi-machine:** Two machines running the same version produce identical SOAP notes from the same transcript text
- [ ] **Patient summary:** Summary contains no CDT codes, no abbreviations, no medical Latin -- verify with a non-medical person reading it

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Session 0 isolation (service cannot access audio) | LOW | Switch from Windows service to Task Scheduler. Remove NSSM dependency. Create scheduled task via installer |
| v1 pipeline broken by v2 changes | MEDIUM | Revert to last green commit. Re-apply v2 changes incrementally with test verification at each step. May lose 1-2 days of work |
| VRAM explosion from diarization model | LOW | Remove diarization model dependency. Fall back to text-based classification. Zero code wasted if text-based was the backup plan |
| Auto-pause false positives | LOW | Increase silence threshold. Add manual confirmation step. Make auto-pause optional (off by default) |
| Installer CUDA DLL mismatch | MEDIUM | Switch from PyInstaller to embedded Python approach. Pin ctranslate2 version per CUDA version. Re-test on all target hardware |
| GPU crash unrecoverable | MEDIUM | Implement process supervisor. Move extraction to subprocess. Requires architecture change but does not affect feature logic |
| Template prompt drift | LOW | Consolidate to single base prompt with addenda. One-time refactor, < 1 day |
| Batch session data loss | HIGH | If sessions are lost, they are gone (audio was discarded). Prevention is the only strategy. Add soft-delete, backup before finalize, session labeling |
| Multi-machine version drift | LOW | Version endpoint + deployment checklist. Manual but sufficient for 3-5 machines |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Session 0 isolation | Installer / Auto-Start | Server starts after reboot with audio access. No Windows service involved |
| v1 pipeline regression | Every v2 phase (meta) | 249+ tests pass after every commit. Zero skipped v1 tests |
| Speaker diarization VRAM | Speaker Identification | Text-based 3-way classification works. No additional ML model loaded. VRAM unchanged from v1 |
| Auto-pause false positives | Batch Workflow | Manual "Next Patient" is primary. Auto-pause is optional with conservative threshold. Tested in real operatory |
| Installer CUDA packaging | Windows Installer | Clean install works on a fresh Windows 10 VM with NVIDIA driver only. No PyInstaller |
| GPU crash recovery | Error Recovery | Server auto-restarts after simulated CUDA crash. Session data survives. < 30 second recovery |
| Template maintenance | Appointment Templates | Single base prompt. Adding a new template type takes < 15 minutes. No prompt duplication |
| Batch session data loss | Batch Workflow | Soft-delete implemented. Accidental finalize recoverable within 24h. Session labeling prevents wrong-session errors |
| Multi-machine version drift | Multi-Machine Deployment | `/version` endpoint. Deployment checklist documented. Installer is machine-aware (auto-detects GPU, mic, CUDA) |

## Sources

- [KB FireDaemon: Windows Session 0 Isolation](https://kb.firedaemon.com/support/solutions/articles/4000086228-microsoft-windows-session-0-isolation-and-interactive-services-detection)
- [GitHub: python-sounddevice query_devices() does not update on Windows (Issue #125)](https://github.com/spatialaudio/python-sounddevice/issues/125)
- [GitHub: python-sounddevice-hotplug fork](https://github.com/melvyn2/python-sounddevice-hotplug)
- [PyTorch Forums: Recover from CUDA Out of Memory](https://discuss.pytorch.org/t/recover-from-cuda-out-of-memory/29051)
- [Saturn Cloud: How to Reset Your GPU After a CUDA Error](https://saturncloud.io/blog/how-to-reset-your-gpu-and-driver-after-a-cuda-error/)
- [PyTorch Forums: CUDA fails to reinitialize after system suspend](https://discuss.pytorch.org/t/cuda-fails-to-reinitialize-after-system-suspend/158108)
- [GitHub: pyannote-audio v4.0.3 uses 6x more VRAM than v3.3.2 (Issue #1963)](https://github.com/pyannote/pyannote-audio/issues/1963)
- [GitHub: speaker-diarization-3.1 high memory usage (Issue #1580)](https://github.com/pyannote/pyannote-audio/issues/1580)
- [Picovoice: Falcon Speaker Diarization -- 100x faster, 5x more accurate](https://picovoice.ai/blog/speaker-diarization/)
- [Picovoice: Adding Speaker Diarization to Whisper using Falcon](https://picovoice.ai/blog/falcon-whisper-integration/)
- [MarkTechPost: Top 9 Speaker Diarization Libraries 2025](https://www.marktechpost.com/2025/08/21/what-is-speaker-diarization-a-2025-technical-guide-top-9-speaker-diarization-libraries-and-apis-in-2025/)
- [Brass Transcripts: Best Speaker Diarization Models 2026](https://brasstranscripts.com/blog/speaker-diarization-models-comparison)
- [GitHub: faster-whisper CUDA compatibility with CTranslate2 (Issue #1086)](https://github.com/SYSTRAN/faster-whisper/issues/1086)
- [GitHub: CTranslate2 not compiled with CUDA support (Issue #1401)](https://github.com/SYSTRAN/faster-whisper/issues/1401)
- [AhmedSyntax: 2026 PyInstaller vs cx_Freeze vs Nuitka](https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/)
- [MSSQL Tips: How to Run a Python Script as a Windows Service using NSSM](https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm/)
- [HELO: Extending Windows Installer (NSIS) with Custom Functionality](https://alpha.helosolutions.ai/2025/03/07/extending-windows-installer-nsis-custom-functionality.html)
- [NVIDIA Forums: Inno Setup deployment of CUDA program](https://forums.developer.nvidia.com/t/inno-setup-deployment-of-cuda-program-in-windows-10/208831)
- [Modal: Choosing Between Whisper Variants](https://modal.com/blog/choosing-whisper-variants)
- [fast.ai: Guide to Recovering from CUDA OOM](https://forums.fast.ai/t/a-guide-to-recovering-from-cuda-out-of-memory-and-other-exceptions/35849)
- [GitHub: dlib -- Cannot recover from CUDA OOM (Issue #1725)](https://github.com/davisking/dlib/issues/1725)

---
*Pitfalls research for: v2.0 feature additions to Dental Notes ambient clinical tool*
*Researched: 2026-03-28*
