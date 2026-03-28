---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: All plans complete
status: complete
stopped_at: Phase 3 Plan 03 complete -- all v1 phases done
last_updated: "2026-03-28T22:46:43Z"
last_activity: 2026-03-28 -- Phase 3 Plan 03 human verification approved. All v1 requirements complete (REV-04 deferred to v2).
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 12
  completed_plans: 12
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment -- every time, with no data leaving the building.
**Methodology:** Pragmatic TDD — test file before implementation, integration tests mandatory, human verification gates are blocking
**Current focus:** All v1 phases complete. 249 tests passing. All 3 human verification gates passed. REV-04 (patient summary) deferred to v2.

## Current Position

Phase: All complete (v1 milestone done)
Current Plan: All plans complete
Status: COMPLETE
Last activity: 2026-03-28 -- Phase 3 Plan 03 human verification approved. All v1 requirements complete.

Progress: [██████████] 100% (All 4 phases complete, all 12 plans complete, all 3 human verification gates passed)

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
- **249 tests passing** across all modules (116 Phase 1/1.1 + 25 clinical models + 15 ollama service + 17 extractor + 9 speaker + 13 integration + 28 session store + 18 formatter + 20 review routes + dictation tests + skipped 13 integration)
- **Review page**: 50/50 side-by-side layout with editable SOAP note and transcript, clipboard copy (Copy All + per-section), regeneration, save, finalize
- **Session list**: Shows saved sessions with timestamp, transcript preview, and colored status badges (Recorded/Extracted/Reviewed)
- **Auto-extraction**: Session stop triggers GPU handoff extraction and redirects to review page
- **Clinical module**: src/dental_notes/clinical/ with Pydantic models, OllamaService, prompts, ClinicalExtractor, SpeakerReattributor
- **ClinicalExtractor**: transcript -> ExtractionResult (SOAP note + CDT codes + clinical_discussion) via OllamaService
- **SpeakerReattributor**: LLM-based speaker label correction preserving chunk boundaries
- **GPU handoff**: extract_with_gpu_handoff() sequences Whisper unload -> LLM -> LLM unload -> Whisper reload
- **Integration tests**: 13 tests with real Ollama + Qwen3 (--integration flag, skipped by default)
- **Human verified SOAP quality**: SOAP notes clinically acceptable for dental transcripts (Phase 2 gate passed)

## Architecture: Speaker Classification

Text-based Doctor/Patient classification in `src/dental_notes/session/speaker.py`:
- **Doctor patterns**: clinical terms (tooth numbers, CDT codes, procedures, materials), assessment language ("I recommend", "let's"), instructions ("open wider", "bite down")
- **Patient patterns**: symptoms ("hurts", "sensitive", "swollen"), questions ("how long", "does insurance"), acknowledgments ("okay", "sounds good")
- **Tie-breaking**: alternates from previous speaker; defaults to Doctor
- No new model dependencies — pure regex keyword matching

Transcript storage changed from flat string to `list[tuple[str, str]]` (speaker, text). SSE sends `<div class="chunk"><strong>Speaker:</strong> text</div>` per chunk. Templates render chunks via Jinja2 `{% for speaker, text in chunks %}`.

## Performance Metrics

**Velocity:**
- Total plans completed: 12 (Phase 1 + Phase 1.1 + Phase 2 Plans 01-03 + Phase 3 Plans 01-03)
- Average duration: 6.4min
- Total execution time: 1.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-streaming-capture | 3 complete | 9min+ | 3min |
| 01.1-test-hardening | 3 of 3 complete | 14min | 4.7min |
| Phase 01.1 P01 | 7min | 2 tasks | 5 files |
| Phase 01.1 P02 | 4min | 2 tasks | 2 files |
| Phase 01.1 P03 | 3min | 2 tasks | 0 files (verification) |
| 02-clinical-extraction | 3 of 3 complete | 33min | 11min |
| Phase 02 P01 | 6min | 2 tasks | 9 files |
| Phase 02 P02 | 7min | 2 tasks | 5 files |
| Phase 02 P03 | 20min | 2 tasks | 7 files (integration + human verification) |
| 03-review-and-export | 3 of 3 complete | 29min | 9.7min |
| Phase 03 P01 | 7min | 2 tasks | 8 files |
| Phase 03 P02 | 8min | 2 tasks | 12 files |
| Phase 03 P03 | 7min + human verification | 2 tasks | 9 files |

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
- [02-03]: pytest --integration flag with pytest_addoption/pytest_collection_modifyitems (integration tests skipped by default)
- [02-03]: Model auto-detection: try qwen3:8b first, fall back to qwen3:4b for 4GB GPU hardware
- [02-03]: clinical_discussion field added to SoapNote during human verification (bullet-point clinical reasoning summary)
- [02-03]: OllamaService schema dereferencing: inline $ref/$defs and strip unsupported keys for Ollama compatibility
- [Phase 3 context]: Auto-extract SOAP note on session stop, with Regenerate button in review screen
- [Phase 3 context]: 50/50 side-by-side layout -- transcript left, SOAP note right, independent scrolling
- [Phase 3 context]: No transcript highlighting -- plain text with speaker labels
- [Phase 3 context]: Clinical Discussion inside SOAP panel as section after CDT codes
- [Phase 3 context]: Full editing on everything -- SOAP note AND transcript are fully editable text areas (type, dictate, cut/copy/paste, add, delete)
- [Phase 3 context]: CDT codes fully editable -- add, remove, modify
- [Phase 3 context]: No read-only sections anywhere -- dentist has complete control
- [Phase 3 context]: Transcript edit triggers "Transcript changed -- Regenerate note?" banner (dentist chooses whether to re-extract)
- [Phase 3 context]: Dictation (mic-to-text) available on any editable field at any stage -- transcript or SOAP note -- using Whisper pipeline for dental term accuracy
- [Phase 3 context]: Note structure is richer than textbook SOAP -- see CONTEXT.md for full format spec
- [Phase 3 context]: Subjective = narrative + bullet point hybrid; Objective = bullet-heavy with some narrative; Assessment = clear-cut; Plan = clear-cut with narrative for justification/contingency
- [Phase 3 context]: Procedure notes (when procedure done after exam): Tx plan + consent noted, then procedure steps/materials in Objective, future plan at end
- [Phase 3 context]: Prescribed medications section always at bottom of note
- [Phase 3 context]: VA patients get additional per-tooth narrative section after the full note (findings + indicated procedures per tooth)
- [Phase 3 context]: Auto-detect exam-only vs exam+procedure from transcript, adjust note format accordingly
- [Phase 3 context]: Auto-detect VA patient from transcript context (VA is mentioned in conversation), auto-generate per-tooth narrative
- [Phase 3 context]: Copy: "Copy All" button + per-section copy icons for granular copying
- [Phase 3 context]: Medications: auto-extract from transcript + dentist can correct and add more, always at bottom of note
- [Phase 3 context]: Finalize button then delete -- explicit "Finalize & Clear" to delete transcript (not auto-delete on copy)
- [Phase 3 context]: Sessions are saveable for later -- dentist can record multiple patients, save sessions, and come back to complete notes later (batch note-writing at end of day)
- [Phase 3 context]: Multiple saved sessions visible in a list -- dentist picks which one to review/complete
- [Phase 3 context]: After finalization, show confirmation + clear path to "New Session" or return to session list
- [Phase 3 context]: Session list shows: timestamp + first line of transcript preview + status badge (Recorded/Extracted/Reviewed)
- [Phase 3 context]: REV-04 (patient summary) deferred -- skip for v1, focus on dentist workflow
- [03-01]: Atomic write via tempfile.mkstemp + os.replace prevents data corruption on interrupted writes
- [03-01]: medications and va_narrative fields defaulted (backward-compatible) so existing extraction pipeline unaffected
- [03-01]: Medications section always at bottom of formatted note, VA narrative conditional (auto-detected)
- [03-01]: edited_note dict overrides SoapNote in formatter (user edits take priority)
- [03-02]: Session stop auto-extracts and redirects to review via HX-Redirect (breaking change from old stop behavior)
- [03-02]: Extraction runs in thread pool via run_in_executor to avoid blocking asyncio event loop
- [03-02]: Server-side note formatting via /api/session/{id}/note-text avoids duplicating formatter logic in JS
- [03-02]: Clipboard fallback using hidden textarea + execCommand for non-secure contexts
- [03-02]: Review page uses full viewport width for 50/50 panel split
- [03-02]: ClinicalExtractor initialization in lifespan wrapped in try/except so server starts without Ollama
- [03-03]: strftime %-I is Linux-only; use %I for Windows compatibility in session list timestamps
- [prompt-v2]: Extraction prompt enriched for dental documentation standards (narrative Subjective with pain details, detailed Objective with all findings, comprehensive CDT coding for all services)
- [prompt-v2]: Procedure documentation section added: consent, anesthetic (type/mg/epi/site), materials, shade, lab info, post-op
- [prompt-v2]: Health history review in Subjective only when discussed (med changes, pre-medication for joints/cardiac devices)
- [prompt-v2]: Strict anti-hallucination: medications EMPTY unless explicitly prescribed, no inferred findings
- [prompt-v3]: Do NOT document absence of findings unless doctor explicitly states the absence — only record what was actually said
- [prompt-v3]: CDT codes for ALL services rendered (diagnostic AND procedural) — exam, radiographs, procedures
- [prompt-v3]: Consolidation/summarization allowed, but no editorialism — straightforward record of conversation

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
10. **Session list 500 on Windows** — strftime('%-I') is Linux-only; changed to %I for cross-platform
11. **ollama Python package missing on Windows** — pip install ollama on Windows Python (was only in WSL venv)

### Pending Todos

- None -- all v1 plans and human verification gates complete

### Blockers/Concerns

- **WSL audio limitation (resolved):** Server must run on Windows Python directly
- Speaker classification accuracy depends on keyword patterns -- may misclassify ambiguous phrases (falls back to alternation). LLM re-attribution (CLI-04) now available via SpeakerReattributor.
- Qwen3 8B quality on dental content validated -- SOAP notes clinically acceptable (human verified)
- Whisper model size constrained by 4GB VRAM floor
- Chunk size tuning: too small = lost context at boundaries, too large = defeats streaming purpose

## Session Continuity

Last session: 2026-03-28
Stopped at: All v1 plans complete. Phase 3 human verification approved.
Resume action: v1 milestone complete. Next steps: v2 requirements (REV-04 patient summary, REC-01/REC-02 recording workflow, ENH-01/02/03 clinical enhancements).

### Phase 1 human verification COMPLETE
Human verified on 2026-03-08: server starts, UI loads, audio captures, Whisper transcribes dental terminology, speaker labels render, transcripts persist, no network requests. Session lifecycle (Start/Pause/Resume/Stop) all functional.

Known limitation accepted: keyword-based speaker classifier loses context across chunks when doctor pauses mid-thought. Now correctable via Phase 2 SpeakerReattributor (CLI-04).

### Phase 2 human verification COMPLETE
Human verified on 2026-03-09: SOAP notes from real dental transcripts are clinically acceptable. Subjective captures chief complaint, Objective references findings, Assessment includes diagnosis, Plan mentions procedures. CDT codes reasonable. Social conversation filtered. clinical_discussion field added during verification.

### Phase 3 human verification COMPLETE
Human verified on 2026-03-28: Full workflow approved -- record, stop, auto-extract, review (50/50 split), edit all sections, transcript dirty tracking + regenerate, copy all + per-section copy, dictation on editable fields, session list with status badges, finalize and clear, batch workflow. 249 automated tests passing. REV-04 (patient summary) deferred to v2 per user decision.

### Files changed (Phase 3 execution + prompt refinement)
- `src/dental_notes/session/store.py` — NEW: SessionStore, SavedSession, SessionStatus (JSON persistence)
- `src/dental_notes/clinical/formatter.py` — NEW: format_note_for_clipboard(), format_section()
- `src/dental_notes/clinical/models.py` — MODIFIED: medications, va_narrative fields, enriched descriptions
- `src/dental_notes/clinical/prompts.py` — MODIFIED: 3 iterations of prompt refinement (narrative, anti-hallucination, transcript-only)
- `src/dental_notes/ui/routes.py` — MODIFIED: 7 review routes, stop auto-extract + HX-Redirect
- `src/dental_notes/ui/dictation.py` — NEW: field-level mic-to-text via Whisper
- `src/dental_notes/main.py` — MODIFIED: lifespan initializes SessionStore, OllamaService, ClinicalExtractor
- `src/dental_notes/templates/review.html` — NEW: 50/50 review page with HTMX extraction + dictation
- `src/dental_notes/templates/_review_note.html` — NEW: SOAP note partial with editable textareas
- `src/dental_notes/templates/_review_transcript.html` — NEW: Transcript textarea with dirty tracking
- `src/dental_notes/templates/_session_list.html` — NEW+FIX: Session card list (strftime fix for Windows)
- `src/dental_notes/templates/sessions.html` — NEW: Standalone session list page
- `src/dental_notes/templates/index.html` — MODIFIED: Added session list section
- `src/dental_notes/static/review.js` — NEW: Clipboard copy, dirty tracking, auto-resize, dictation
- `src/dental_notes/static/style.css` — MODIFIED: Review layout, panel, badge, dictation, finalize styles
- `tests/test_session_store.py` — NEW: 28 tests
- `tests/test_note_formatter.py` — NEW: 18 tests
- `tests/test_review_routes.py` — NEW: 20 tests
- `tests/test_dictation.py` — NEW: dictation endpoint tests
- `tests/test_routes.py` — MODIFIED: Updated stop tests for new HX-Redirect behavior
- `tests/conftest.py` — MODIFIED: FakeSessionStore, sample fixtures
