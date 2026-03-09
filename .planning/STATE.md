---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 02-02 complete, next is 02-03
status: executing
stopped_at: Completed 02-02-PLAN.md
last_updated: "2026-03-09T06:35:12.535Z"
last_activity: 2026-03-09 -- Plan 02-02 complete (ClinicalExtractor + SpeakerReattributor + GPU handoff)
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 9
  completed_plans: 8
  percent: 89
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment -- every time, with no data leaving the building.
**Methodology:** Pragmatic TDD — test file before implementation, integration tests mandatory, human verification gates are blocking
**Current focus:** Phase 2 (Clinical Extraction) in progress. Plan 02 complete, Plan 03 (integration test) next.

## Current Position

Phase: 2 of 4 (Clinical Extraction) -- IN PROGRESS
Current Plan: 02-02 complete, next is 02-03
Status: Phase 2 In Progress (2/3 plans done)
Last activity: 2026-03-09 -- Plan 02-02 complete (ClinicalExtractor + SpeakerReattributor + GPU handoff)

Progress: [█████████░] 89%

## What Works Now

- **Server runs on Windows Python** with 55 audio devices detected (Yeti Classic mic)
- **Full session lifecycle**: Start → Record → Pause → Resume → Stop — all verified
- **Whisper transcription**: Ambient speech transcribed correctly via faster-whisper (int8/CUDA)
- **SSE streaming**: Transcript chunks stream to browser as structured `<div class="chunk">` elements
- **Speaker labels**: Each chunk classified as "Doctor" or "Patient" via text-based keyword analysis
- **Paragraph separation**: Each speaker turn rendered as a separate visual block with spacing
- **Transcript persists after stop**: Chunks remain visible in UI after session ends (was disappearing before)
- **Multiple sessions**: Stop → Start cycle works (OOB swap gives fresh SSE connection each time)
- **Transcript files saved**: Plain text with speaker labels, one per session, in `transcripts/` directory
- **182 tests passing** across all modules (116 Phase 1/1.1 + 25 clinical models + 15 ollama service + 17 extractor + 9 speaker)
- **Clinical module**: src/dental_notes/clinical/ with Pydantic models, OllamaService, prompts, ClinicalExtractor, SpeakerReattributor
- **ClinicalExtractor**: transcript -> ExtractionResult (SOAP note + CDT codes) via OllamaService
- **SpeakerReattributor**: LLM-based speaker label correction preserving chunk boundaries
- **GPU handoff**: extract_with_gpu_handoff() sequences Whisper unload -> LLM -> LLM unload -> Whisper reload

## Architecture: Speaker Classification

Text-based Doctor/Patient classification in `src/dental_notes/session/speaker.py`:
- **Doctor patterns**: clinical terms (tooth numbers, CDT codes, procedures, materials), assessment language ("I recommend", "let's"), instructions ("open wider", "bite down")
- **Patient patterns**: symptoms ("hurts", "sensitive", "swollen"), questions ("how long", "does insurance"), acknowledgments ("okay", "sounds good")
- **Tie-breaking**: alternates from previous speaker; defaults to Doctor
- No new model dependencies — pure regex keyword matching

Transcript storage changed from flat string to `list[tuple[str, str]]` (speaker, text). SSE sends `<div class="chunk"><strong>Speaker:</strong> text</div>` per chunk. Templates render chunks via Jinja2 `{% for speaker, text in chunks %}`.

## Performance Metrics

**Velocity:**
- Total plans completed: 8 (Phase 1 + Phase 1.1 + Phase 2 Plans 01-02)
- Average duration: 5.1min
- Total execution time: 0.60 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-streaming-capture | 3 complete | 9min+ | 3min |
| 01.1-test-hardening | 3 of 3 complete | 14min | 4.7min |
| Phase 01.1 P01 | 7min | 2 tasks | 5 files |
| Phase 01.1 P02 | 4min | 2 tasks | 2 files |
| Phase 01.1 P03 | 3min | 2 tasks | 0 files (verification) |
| 02-clinical-extraction | 2 of 3 complete | 13min | 6.5min |
| Phase 02 P01 | 6min | 2 tasks | 9 files |
| Phase 02 P02 | 7min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Pipeline-first approach -- prove capture+transcribe before building UI
- [Roadmap]: Sequential GPU model loading -- Whisper and LLM cannot coexist in 8GB VRAM
- [Roadmap]: COARSE granularity -- 3 phases following natural pipeline boundaries
- [Revision]: Streaming architecture -- audio chunks transcribed and discarded immediately, no full WAV stored
- [Revision]: Merged audio capture + transcription into single phase (inseparable with ephemeral chunks)
- [Revision]: GTX 1050 (4GB VRAM) is the target floor -- small Whisper model required
- [01-01]: FakeVadModel test double avoids downloading real silero-vad model in CI
- [01-01]: Simple word-level overlap matching (not fuzzy) as correct starting point
- [01-01]: Plain text transcript format with no JSON or timestamps per locked decisions
- [01-02]: Lazy import of faster_whisper inside load_model() avoids CUDA dependency at import time
- [01-02]: Factory methods (_create_capture, _create_chunker) enable dependency injection in tests
- [01-02]: Daemon processing thread ensures Whisper inference never blocks asyncio event loop
- [01-03]: Deferred Whisper model loading -- load on first session start, not at app startup (was blocking lifespan 10+ seconds)
- [01-03]: Host changed from 127.0.0.1 to 0.0.0.0 -- required for WSL→Windows browser access
- [01-03]: Server must run on Windows Python -- WSL has no PortAudio/audio hardware access
- [01-03]: Created setup_windows.py and start_server.py for Windows-native execution
- [01-03]: OOB swap for transcript area -- HTMX SSE extension caches internal state on DOM elements; must replace element entirely (outerHTML) on session start/stop for clean SSE reconnection
- [01-03]: Route error handling catches all exceptions (not just RuntimeError) and returns error banners in UI
- [01-03]: Fast-fail on audio device -- AudioCapture.start() runs first before downloading VAD model or loading Whisper
- [01-03]: _transcript.html is state-aware -- includes SSE attributes when recording (fixes page refresh during active session)
- [speaker]: Text-based classification chosen over audio diarization -- no new model deps, no VRAM cost, sufficient accuracy for dental context
- [speaker]: Transcript restructured from flat string to chunk list -- enables proper HTML rendering per speaker turn
- [speaker]: SSE sends `<div class="chunk">` elements instead of `<span>` with embedded newlines -- reliable cross-browser rendering
- [methodology]: Pragmatic TDD adopted -- v1 had 128 tests and zero working product; tests must verify behavior the user cares about, not mock internals
- [methodology]: Test file before implementation file; integration tests mandatory per phase; human checkpoints are blocking gates
- [methodology]: Phase 1.1 inserted to harden Phase 1 test coverage before moving to Phase 2
- [01.1-01]: Import fakes via `from tests.conftest import` since tests/ has __init__.py (package mode)
- [01.1-01]: Mock pynput via sys.modules patching to avoid X display requirement on headless Linux
- [01.1-01]: Test AudioCapture by calling _audio_callback directly with numpy arrays, not opening real streams
- [Phase 01.1]: Import fakes via from tests.conftest import since tests/ has __init__.py (package mode)
- [Phase 01.1]: Mock pynput via sys.modules patching to avoid X display requirement on headless Linux
- [01.1-02]: Integration test uses real VadDetector with FakeVadModel injected via _model attribute, not mock.patch
- [01.1-02]: Tuned Settings for integration test (short chunk duration/silence gap) for fast execution
- [01.1-02]: Lifespan shutdown tested structurally via FakeSessionManager rather than asgi-lifespan library
- [Phase 01.1]: [01.1-03]: Phase 1 pipeline verified working on real Windows hardware with NVIDIA GPU and Yeti Classic microphone
- [Phase 01.1]: [01.1-03]: Speaker keyword classifier limitation deferred to Phase 2 CLI-04 for LLM re-attribution
- [02-01]: CDT reference embedded as string constant in prompts.py (45 common codes) rather than external file
- [02-01]: FakeOllamaService nests cdt_codes inside soap_note matching ExtractionResult schema
- [02-01]: OllamaService uses ollama.Client sync API (not async) for simplicity
- [02-01]: /nothink prefix prepended to all user content to disable Qwen3 thinking mode
- [02-02]: FakeWhisperServiceGpu as separate class from FakeWhisperService to avoid breaking 156 existing tests
- [02-02]: Speaker system prompt separate from EXTRACTION_SYSTEM_PROMPT (focused on attribution only)
- [02-02]: _SpeakerChunkList Pydantic wrapper model for structured LLM array output schema
- [02-02]: GPU handoff pattern: whisper.unload() -> extract() -> finally { ollama.unload(); whisper.load_model() }

### Bugs Fixed (All Sessions)

1. **500 on /session/start** — routes only caught RuntimeError, not OSError/PortAudioError from sounddevice
2. **Duplicate #transcript-area on page** — _session.html unconditionally included _transcript_oob.html, creating 2 elements with same ID on initial render; broke HTMX targeting and buttons
3. **SSE not reconnecting after stop→start** — HTMX SSE extension caches state on DOM elements; fixed with OOB outerHTML swap to replace element entirely
4. **VadDetector __new__ hack** — was bypassing __init__; fixed to use proper constructor
5. **Audio capture ordering** — moved capture.start() before VAD/Whisper loading for fast-fail on missing device
6. **HTMX CDN redirect** — changed to direct /dist/htmx.min.js path
7. **Transcript disappears on stop** — stop route didn't pass transcript to template; now passes `chunks` list
8. **One big paragraph / no speaker separation** — flat string + `\n\n` in `<span>` unreliable via SSE; restructured to chunk list with `<div>` elements
9. **No speaker labels** — added text-based classifier, integrated into processing loop and templates

### Pending Todos

- Execute Phase 2 Plan 03 (Integration test with real Ollama + human verification checkpoint)

### Blockers/Concerns

- **WSL audio limitation (resolved):** Server must run on Windows Python directly
- Speaker classification accuracy depends on keyword patterns -- may misclassify ambiguous phrases (falls back to alternation)
- Qwen3 8B quality on dental content is unvalidated -- may need model fallback (Phase 2)
- Whisper model size constrained by 4GB VRAM floor
- Chunk size tuning: too small = lost context at boundaries, too large = defeats streaming purpose

## Session Continuity

Last session: 2026-03-09T06:34:57.739Z
Stopped at: Completed 02-02-PLAN.md
Resume action: Execute Phase 2 Plan 03 (Integration test with real Ollama + human verification)

### How to resume
1. Execute Phase 2 Plan 03 -- Integration test with real Ollama + human verification checkpoint

### Phase 1 human verification COMPLETE
Human verified on 2026-03-08: server starts, UI loads, audio captures, Whisper transcribes dental terminology, speaker labels render, transcripts persist, no network requests. Session lifecycle (Start/Pause/Resume/Stop) all functional.

Known limitation accepted: keyword-based speaker classifier loses context across chunks when doctor pauses mid-thought. Deferred to Phase 2 CLI-04 for LLM re-attribution.

### Files changed this session
- `src/dental_notes/clinical/extractor.py` — NEW: ClinicalExtractor with extract(), extract_from_chunks(), extract_with_gpu_handoff()
- `src/dental_notes/clinical/speaker.py` — NEW: SpeakerReattributor with reattribute() and SPEAKER_SYSTEM_PROMPT
- `tests/test_extractor.py` — NEW: 17 tests for extraction pipeline and GPU handoff
- `tests/test_speaker_reattribution.py` — NEW: 9 tests for speaker re-attribution
- `tests/conftest.py` — MODIFIED: FakeWhisperServiceGpu, SAMPLE_DENTAL_TRANSCRIPT, unload_count on FakeOllamaService
- `.planning/phases/02-clinical-extraction/02-02-SUMMARY.md` — NEW: Plan 02 summary
- `.planning/STATE.md` — Updated: Phase 2 Plan 02 complete
- `.planning/ROADMAP.md` — Updated: Phase 2 progress
