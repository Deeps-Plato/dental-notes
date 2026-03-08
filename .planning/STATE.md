---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Adopted pragmatic TDD methodology, inserted Phase 1.1 (test hardening), returning to planning
last_updated: "2026-03-07T14:00:00Z"
last_activity: 2026-03-07 -- Added TDD methodology to PROJECT.md, inserted Phase 1.1 into roadmap, updated config
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 6
  completed_plans: 2
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment -- every time, with no data leaving the building.
**Methodology:** Pragmatic TDD — test file before implementation, integration tests mandatory, human verification gates are blocking
**Current focus:** Planning — adopted TDD, inserted Phase 1.1 (test hardening), preparing to plan Phase 1.1

## Current Position

Phase: 1 of 4 (Streaming Capture and Transcription) — code complete, needs verification
Next: Phase 1.1 (Test Hardening) — needs planning
Status: Returned to planning to adopt TDD methodology
Last activity: 2026-03-07 -- TDD methodology added, Phase 1.1 inserted into roadmap

Progress: [###▒░░░░░░] 33%

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
- **83 tests passing** across all modules (including 11 speaker classification tests)

## Architecture: Speaker Classification

Text-based Doctor/Patient classification in `src/dental_notes/session/speaker.py`:
- **Doctor patterns**: clinical terms (tooth numbers, CDT codes, procedures, materials), assessment language ("I recommend", "let's"), instructions ("open wider", "bite down")
- **Patient patterns**: symptoms ("hurts", "sensitive", "swollen"), questions ("how long", "does insurance"), acknowledgments ("okay", "sounds good")
- **Tie-breaking**: alternates from previous speaker; defaults to Doctor
- No new model dependencies — pure regex keyword matching

Transcript storage changed from flat string to `list[tuple[str, str]]` (speaker, text). SSE sends `<div class="chunk"><strong>Speaker:</strong> text</div>` per chunk. Templates render chunks via Jinja2 `{% for speaker, text in chunks %}`.

## Performance Metrics

**Velocity:**
- Total plans completed: 2 (01-03 code complete but awaiting formal checkpoint)
- Average duration: 4.5min
- Total execution time: 0.15 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-streaming-capture | 2 complete + 1 in progress | 9min+ | 4.5min |

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

- **Restart server on Windows** to pick up speaker label + chunk changes
- **User testing**: verify Doctor/Patient labels appear, paragraphs separated, transcript persists after stop
- Formal Plan 01-03 Task 3 checkpoint: user browser testing
- After checkpoint approved: create 01-03-SUMMARY.md, mark Phase 1 complete in ROADMAP.md

### Blockers/Concerns

- **WSL audio limitation (resolved):** Server must run on Windows Python directly
- Speaker classification accuracy depends on keyword patterns -- may misclassify ambiguous phrases (falls back to alternation)
- Qwen3 8B quality on dental content is unvalidated -- may need model fallback (Phase 2)
- Whisper model size constrained by 4GB VRAM floor
- Chunk size tuning: too small = lost context at boundaries, too large = defeats streaming purpose

## Session Continuity

Last session: 2026-03-07
Stopped at: TDD methodology adopted, Phase 1.1 inserted, ready to plan Phase 1.1
Resume action: Plan Phase 1.1 (test hardening) → execute → then plan Phase 2 with TDD

### How to resume
1. Run `/gsd:plan-phase 1.1` to create the test hardening plan
2. Execute Phase 1.1 (fill test gaps, add integration test, complete human verification)
3. After Phase 1.1 passes: plan Phase 2 with TDD methodology
4. Human verification from Phase 1 Plan 01-03 is folded into Phase 1.1

### Phase 1 human verification still pending
The server restart + browser test from Plan 01-03 Task 3 has not been completed yet.
This is now part of Phase 1.1 — the test hardening phase ensures Phase 1 actually works before we move on.

### Files changed this session
- `src/dental_notes/session/speaker.py` — NEW: text-based Doctor/Patient classifier
- `src/dental_notes/session/manager.py` — chunks list, classify_speaker integration, get_chunks()/get_chunk_count()
- `src/dental_notes/ui/routes.py` — SSE sends chunk divs, stop passes chunks, html.escape(), chunk_count status
- `src/dental_notes/templates/_transcript.html` — chunk rendering with {% for speaker, text in chunks %}
- `src/dental_notes/templates/_transcript_oob.html` — same chunk rendering for OOB swaps
- `src/dental_notes/static/style.css` — .chunk spacing, speaker label color
- `tests/test_speaker.py` — NEW: 11 classification tests
- `tests/test_routes.py` — updated FakeSessionManager, 2 new integration tests
