# Project Research Summary

**Project:** Ambient Dental Note-Taking (local-first)
**Domain:** Clinical AI -- ambient speech-to-text transcription and structured SOAP note generation for dental practices
**Researched:** 2026-03-05
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project is a local-first ambient clinical documentation tool for dental practices. It records appointment audio, transcribes it with a local Whisper model, filters out non-clinical conversation, and generates structured SOAP notes via a local LLM -- all without any data leaving the office network. The competitive landscape is entirely cloud-based SaaS (Freed AI, Overjet Voice, Denti.AI, VideaHealth, Bola AI) at $149-399/month per provider. The local-only approach is the primary differentiator: zero recurring cost, zero PHI exposure to third parties, and no BAA negotiations. Every major competitor requires cloud processing.

The recommended approach is a sequential batch pipeline: record the full appointment to disk, then transcribe with faster-whisper (large-v3-turbo INT8), then structure with a local LLM (Qwen3 8B via Ollama) -- all running on existing NVIDIA GPUs (GTX 1070 Ti, 8GB VRAM). The architecture is deliberately simple: a single FastAPI process serving an HTMX browser UI at localhost, with Ollama as the only external dependency. No JavaScript framework, no Docker, no build step, no Electron. The user already has proven experience with faster-whisper, sounddevice, silero-vad, and FastAPI from the whisper-ptt and previous dental-notes projects.

The critical risks are (1) the "demo trap" -- the previous attempt at this project produced 128 tests across 8 phases but never generated a real dental note from a real recording, so this rebuild must prove the core pipeline works before building any infrastructure; (2) Whisper hallucinations on silent segments common during dental procedures; (3) dental equipment noise (70-87 dB handpieces, 89 dB suction) destroying transcription accuracy unless the right microphone is used; (4) local LLM note quality being insufficient for clinical use without extensive prompt engineering and dentist evaluation; and (5) Florida two-party consent law compliance, which makes recording without explicit consent a felony. Mitigation strategies exist for all of these, but they must be addressed in the earliest phases, not retrofitted.

## Key Findings

### Recommended Stack

The stack leverages Python 3.12 and existing GPU hardware. All core ML components are proven: faster-whisper and silero-vad are already running in the user's whisper-ptt project. The only new components are Ollama for local LLM inference and pyannote-audio for speaker diarization. The application framework is FastAPI + HTMX (server-rendered HTML, no build step), which mirrors patterns the user has successfully deployed in dental-notes and tax-shield.

**Core technologies:**
- **faster-whisper (large-v3-turbo INT8):** Speech-to-text -- 6x faster than large-v3, near-equivalent accuracy, ~2GB VRAM. Already proven in whisper-ptt.
- **Ollama + Qwen3 8B (Q4_K_M):** Local LLM for clinical content extraction and SOAP note structuring -- 5.2GB download, structured JSON output, Apache 2.0 license.
- **silero-vad:** Voice activity detection -- <1ms latency, prevents Whisper hallucinations on silence. Already used in whisper-ptt.
- **sounddevice:** Audio capture from microphone -- PortAudio bindings, callback-based streaming. Already used in whisper-ptt.
- **FastAPI + HTMX:** Web application framework -- single Python process, browser-based UI at localhost, no build step, SSE for status updates.
- **pyannote-audio (v4.0):** Speaker diarization -- separates dentist/patient/assistant voices, DER ~11-19%. Phase 2+ enhancement.
- **SQLite:** Session management and state tracking -- no separate database server needed.

**Critical version requirement:** All PyTorch packages must use CUDA 12.1 (cu121 index URL). Mixing CUDA versions causes silent failures.

### Expected Features

**Must have (table stakes -- v1 launch):**
- Ambient audio recording with start/stop per appointment
- Recording consent gate (Florida two-party consent -- felony without it)
- Local Whisper transcription with dental vocabulary prompt
- Clinical content filtering (separate clinical speech from chitchat)
- Structured SOAP note generation (dental-specific sections)
- Side-by-side review UI (transcript + editable SOAP draft)
- One-click copy to clipboard (formatted for Dentrix paste)
- Ephemeral data cleanup (delete audio/transcript after finalization)
- Session management (track today's appointments)

**Should have (v1.x after core is proven):**
- CDT procedure code suggestions from Assessment/Plan sections
- Appointment-type templates (exam, restorative, hygiene, extraction, endo)
- Expanded dental terminology Whisper prompt
- Speaker diarization (dentist vs. patient vs. assistant)
- Post-visit patient summary (plain-language)

**Defer (v2+):**
- Voice-activated perio charting (extremely high accuracy bar, separate validation cycle)
- Multi-provider support
- Referral letter generation
- Treatment plan generation with cost estimates

**Anti-features (explicitly avoid):**
- Real-time streaming transcription (distracts dentist, worse accuracy, massive complexity)
- Dentrix API integration (proprietary, poorly documented, unnecessary -- copy-paste suffices)
- Patient identity/records database (creates PHI liability -- Dentrix is the system of record)
- Always-on continuous recording (legal nightmare in two-party consent state)
- Autonomous note finalization without clinician review (malpractice risk)

### Architecture Approach

The system is a single-process FastAPI application serving a browser-based UI at localhost. Audio is recorded to disk as WAV, then processed through a sequential batch pipeline: transcription (faster-whisper) followed by clinical extraction (Ollama LLM). GPU models are loaded sequentially, never concurrently, to fit within 8GB VRAM. Sessions follow a strict state machine (RECORDING -> RECORDED -> TRANSCRIBING -> TRANSCRIBED -> EXTRACTING -> DRAFTED -> FINALIZED -> PURGED) with automated ephemeral cleanup.

**Major components:**
1. **Audio Capture** (`audio/`) -- sounddevice recording to WAV, mic enumeration, VAD preprocessing
2. **Transcription Engine** (`transcription/`) -- faster-whisper transcription, word alignment, speaker diarization
3. **Clinical Extractor** (`extraction/`) -- Ollama client, SOAP note prompt templates, CDT code mapping
4. **Session Manager** (`sessions/`) -- SQLite-backed state machine, lifecycle tracking, ephemeral cleanup
5. **Web UI** (`routes/` + `templates/`) -- HTMX-based dashboard, recording controls, side-by-side review, copy-to-clipboard
6. **Config Manager** (`config.py`) -- JSON-backed settings for mic selection, model preferences, note templates

### Critical Pitfalls

1. **The Demo Trap** -- The previous attempt built Flutter UI, FastAPI backend, SQLCipher, biometric auth, and 128 tests across 8 phases but never produced a real dental note from a real recording. Prevention: Each phase must produce a concrete, demonstrable artifact. No UI or infrastructure until the core pipeline (record -> transcribe -> structure) works end-to-end in a terminal.

2. **Whisper Hallucinations** -- Whisper fabricates text during silence (~1.4% of transcriptions, 40% potentially harmful). Dental appointments have extended silences during procedures. Prevention: Use silero-vad to segment audio before transcription; only pass speech-containing segments to Whisper. Use `condition_on_previous_text=False` and tune `no_speech_threshold`.

3. **Dental Equipment Noise** -- Handpieces at 70-87 dB and suction at 89 dB destroy transcription when using room microphones. Prevention: Use a directional lapel/lavalier microphone on the dentist. Test audio quality with equipment running BEFORE building software. This is a hardware problem that software cannot solve.

4. **GPU VRAM Exhaustion** -- GTX 1070 Ti (8GB) cannot hold both Whisper (~2GB) and Qwen3 8B (~6GB) simultaneously. Prevention: Run models sequentially, never concurrently. Keep Whisper loaded by default, load LLM only for extraction, then swap back.

5. **Florida Two-Party Consent** -- Recording without all-party consent is a third-degree felony (up to 5 years, $5,000 fine). Prevention: Consent gate in software that prevents recording from starting. Add recording consent to patient intake forms. Handle mid-appointment arrivals with pause/resume.

6. **LLM Note Quality** -- Local 8B models produce hallucinated clinical details (~1.47%) and omit critical information (~3.45%). Prevention: Treat LLM output as draft only, require clinician review, use structured prompts with explicit SOAP sections and dental terminology, test with 20+ real transcripts before considering the feature complete.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Audio Capture and Hardware Validation
**Rationale:** The previous project failed because it built infrastructure before proving the core pipeline. This phase must produce a real WAV recording from a real dental appointment environment. Microphone selection and placement against dental noise is a hardware problem that must be validated before any software pipeline can succeed.
**Delivers:** Working audio recording to disk with mic selection, VAD preprocessing, and consent gate UI. A playable WAV file from a dental operatory with acceptable speech quality.
**Addresses:** Ambient audio recording, recording consent gate, session management (start/stop)
**Avoids:** Demo trap (Pitfall 1), dental equipment noise (Pitfall 3), Florida consent violations (Pitfall 6), HIPAA file handling (Pitfall 5)

### Phase 2: Transcription Pipeline
**Rationale:** Depends on Phase 1 producing valid audio files. Transcription quality determines everything downstream. Hallucination prevention (VAD segmentation) must be built in from the start.
**Delivers:** Accurate dental transcripts from recorded appointments. Dental vocabulary prompt optimization. Hallucination mitigation via VAD preprocessing.
**Addresses:** Local Whisper transcription, dental terminology optimization
**Avoids:** Whisper hallucinations (Pitfall 2), GPU VRAM exhaustion (Pitfall 4)

### Phase 3: Clinical Extraction and SOAP Note Generation
**Rationale:** Depends on Phase 2 producing accurate transcripts. This is where the local LLM is introduced. Prompt engineering is iterative and requires real transcript data from Phase 2 to tune. The Ollama integration and structured JSON output are well-documented.
**Delivers:** Structured SOAP notes from dental transcripts. Clinical content filtering (chitchat removal). CDT code suggestions.
**Addresses:** Clinical content filtering, SOAP note generation, CDT code suggestions
**Avoids:** LLM note quality (Pitfall 7), GPU VRAM exhaustion (Pitfall 4 -- sequential model loading)

### Phase 4: Review UI and End-to-End Pipeline
**Rationale:** Depends on Phases 1-3 producing working output. The review workflow is where all components integrate. This is also where automation bias must be designed against -- the UI must force meaningful clinician review.
**Delivers:** Complete end-to-end workflow: record -> transcribe -> extract -> review -> copy -> cleanup. Side-by-side transcript + SOAP note editor. Copy-to-clipboard for Dentrix. Ephemeral data cleanup after finalization.
**Addresses:** Review and edit workflow, copy to clipboard, ephemeral data cleanup
**Avoids:** Automation bias (Pitfall 8), HIPAA violations from lingering files (Pitfall 5)

### Phase 5: Speaker Diarization and Templates
**Rationale:** Enhancement phase. Speaker diarization improves clinical filtering accuracy by attributing speech to dentist vs. patient. Appointment-type templates improve SOAP note structure. Both depend on a working core pipeline.
**Delivers:** Speaker-labeled transcripts, appointment-type templates (exam, restorative, hygiene, endo, extraction), post-visit patient summaries.
**Addresses:** Speaker diarization, appointment-type templates, post-visit patient summary
**Avoids:** Premature speaker identification (build on proven pipeline)

### Phase 6: Polish, Hardening, and Multi-Appointment
**Rationale:** Production readiness. Error handling for all failure modes (GPU OOM, Ollama down, mic unavailable), startup health checks, multi-appointment sequencing without memory leaks, auto-cleanup of abandoned sessions.
**Delivers:** Robust system that handles 5-10 appointments/day reliably. System tray icon for background operation. Configuration UI.
**Addresses:** Session management (full), error recovery, production stability
**Avoids:** Performance traps (cold model loading, UI blocking, context window overflow)

### Phase Ordering Rationale

- **Pipeline-first, infrastructure-after:** Research overwhelmingly indicates that the previous attempt failed by building infrastructure before proving the pipeline. Phases 1-3 each produce a concrete artifact (WAV file, transcript, SOAP note) that can be manually verified before proceeding.
- **Bottom-up component independence:** Audio capture, transcription, session management, and clinical extraction can each be developed and tested independently (Phases 1-3). Phase 4 integrates them. This matches the architecture's clean component boundaries.
- **GPU resource sequencing:** Whisper and the LLM share one GPU. The pipeline must be designed for sequential model loading from the start (Phase 2 and Phase 3 enforce this).
- **Diarization is additive:** Speaker diarization (Phase 5) layers onto the existing transcription pipeline without restructuring. It enhances quality but is not required for the core value proposition.
- **Legal compliance from day one:** Consent gate is in Phase 1, not a later add-on. HIPAA-compliant file handling is in Phase 1. These cannot be retrofitted.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Microphone hardware selection for dental operatory -- needs hands-on testing with real equipment noise. No amount of software research replaces plugging in a mic and recording a real appointment.
- **Phase 3:** LLM prompt engineering for dental SOAP notes -- Qwen3 8B dental-specific quality is unknown. Requires iterative testing with real transcripts. May need to fall back to Llama 3.1 8B or Phi-4-mini.
- **Phase 5:** pyannote-audio v4.0 VRAM usage -- v4.0.3 uses 6x more VRAM than v3.3.2 (known issue #1963). Must benchmark on target hardware.

Phases with standard patterns (skip research-phase):
- **Phase 2:** faster-whisper transcription is well-documented, user has existing whisper-ptt codebase to build from. silero-vad integration is proven.
- **Phase 4:** FastAPI + HTMX UI is a well-established pattern. User has extensive FastAPI experience. Copy-to-clipboard and session CRUD are straightforward.
- **Phase 6:** Error handling, health checks, and system tray (pystray) are standard Python patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core technologies are proven (faster-whisper, sounddevice, silero-vad used in whisper-ptt; FastAPI used in dental-notes and tax-shield). Ollama is well-documented. Only uncertainty is Qwen3 8B quality on dental content. |
| Features | HIGH | Feature landscape mapped against 6+ competitors with peer-reviewed research. MVP scope is clear. Anti-features are well-justified. |
| Architecture | HIGH | Single-process FastAPI + batch pipeline is the simplest viable architecture. GPU time-sharing and session state machine are well-designed. Component boundaries are clean. |
| Pitfalls | HIGH | 8 pitfalls identified from peer-reviewed medical AI literature, regulatory statutes, and the user's own failed previous attempt. Each has concrete prevention strategies. |

**Overall confidence:** MEDIUM-HIGH

The HIGH confidence in stack, features, architecture, and pitfalls is tempered by two MEDIUM-confidence unknowns that can only be resolved empirically:
1. Local LLM quality on dental SOAP notes (Qwen3 8B has not been tested on dental content)
2. Microphone hardware performance in a real dental operatory with equipment noise

### Gaps to Address

- **Dental LLM quality:** No dental-specific benchmarks exist for Qwen3 8B or any local 8B model. Must generate 20+ test notes and have the dentist grade them during Phase 3. If no local model is adequate, the architecture may need to support an optional cloud LLM fallback (with BAA) for higher quality.
- **Microphone selection:** Research identifies the problem (dental noise) and general solution (lapel mic), but specific product recommendations need real-world testing in Phase 1. The user should test 2-3 mic options.
- **Consent form language:** Must be reviewed by a Florida healthcare attorney. Template language from the internet is insufficient for the intersection of HIPAA + Florida wiretapping law + dental regulatory requirements.
- **VRAM budget on GTX 1050 (4GB):** If some office machines have GTX 1050 cards, the model selection changes significantly (small.en Whisper + Phi-4-mini LLM). Need to confirm minimum hardware spec.
- **Ollama keep_alive behavior:** How quickly does Ollama unload models when switching between Whisper and LLM? Cold-start latency needs benchmarking.
- **Long appointment transcripts:** A 30-minute appointment generates ~3000+ words. Qwen3 8B has 32K context, which should be sufficient, but KV cache at long contexts uses significant VRAM. Must test with realistic transcript lengths.

## Sources

### Primary (HIGH confidence)
- [SYSTRAN/faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- model sizes, compute types, benchmarks
- [snakers4/silero-vad GitHub](https://github.com/snakers4/silero-vad) -- v6.2.1, streaming VAD
- [pyannote/pyannote-audio GitHub](https://github.com/pyannote/pyannote-audio) -- v4.0, diarization pipeline
- [Ollama structured outputs](https://ollama.com/blog/structured-outputs) -- JSON schema mode
- [Qwen3-8B HuggingFace](https://huggingface.co/Qwen/Qwen3-8B) -- model architecture, context window
- [Whisper Large V3 Turbo HuggingFace](https://huggingface.co/openai/whisper-large-v3-turbo) -- turbo variant specs
- [Whisper prompting guide (OpenAI Cookbook)](https://cookbook.openai.com/examples/whisper_prompting_guide) -- initial_prompt usage
- [Florida Statute 934.03](https://recordinglaw.com/party-two-party-consent-states/florida-recording-laws/) -- two-party consent, felony penalties
- [PMC: Dental Clinic Noise Levels](https://pmc.ncbi.nlm.nih.gov/articles/PMC9776681/) -- 70-89 dB equipment noise
- [NEJM AI: Ambient AI Scribes Randomized Trial](https://ai.nejm.org/doi/abs/10.1056/AIoa2501000) -- 238 physicians, 72K encounters
- [PMC: AI Scribe Documentation Quality](https://pmc.ncbi.nlm.nih.gov/articles/PMC12638734/) -- 19.5% transcript error transmission
- [PMC: Beyond Human Ears -- Risks of AI Scribes](https://pmc.ncbi.nlm.nih.gov/articles/PMC12460601/) -- hallucination, automation bias
- [ADA SOAP Note Standards](https://www.ada.org/resources/practice/practice-management/templates-smart-phrases-and-soap) -- official guidance

### Secondary (MEDIUM confidence)
- [Competitor analyses](https://www.getfreed.ai/, https://www.overjet.com/, https://www.denti.ai/, https://bola.ai/) -- feature comparison
- [PMC: Informed Consent for Ambient Documentation](https://pmc.ncbi.nlm.nih.gov/articles/PMC12284739/) -- consent models
- [Picovoice VAD Comparison 2025](https://picovoice.ai/blog/best-voice-activity-detection-vad-2025/) -- Silero vs WebRTC
- [LocalLLM.in: Best LLMs for 8GB VRAM](https://localllm.in/blog/best-local-llms-8gb-vram-2025) -- model comparison
- [Oral Health Group: AI transcription dental](https://www.oralhealthgroup.com/) -- dental Whisper accuracy study

### Tertiary (LOW confidence)
- Qwen3 8B performance on dental terminology -- no direct benchmarks found, needs empirical validation
- Microphone product recommendations for dental operatory -- general guidance only, needs hands-on testing

---
*Research completed: 2026-03-05*
*Ready for roadmap: yes*
