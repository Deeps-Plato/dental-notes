---
phase: 05-workflow-and-recovery
plan: 02
subsystem: session
tags: [auto-pause, rolling-buffer, next-patient, auto-save, mic-disconnect, whisper-oom, state-machine]

# Dependency graph
requires:
  - phase: 05-workflow-and-recovery
    provides: Phase 5 config settings, SessionStore INCOMPLETE CRUD, HealthChecker
provides:
  - SessionManager.AUTO_PAUSED state with silence-triggered transitions and speech resume
  - Rolling audio buffer (deque) during auto-pause with replay into chunker on resume
  - next_patient() flow for batch multi-patient days (stop + save + start, no extraction)
  - Periodic auto-save of incomplete sessions (chunk threshold + time interval)
  - Mic disconnect detection via block arrival timing with auto-save and error flag
  - _transcribe_with_retry() with GPU OOM retry, cache clearing, and raw audio fallback save
  - Session ID generation and tracking (uuid4 per session)
  - FakeVadDetector in conftest for controllable VAD testing
affects: [05-workflow-and-recovery]

# Tech tracking
tech-stack:
  added: []
  patterns: [rolling deque buffer for auto-pause audio, OOM retry with raw audio fallback, mic disconnect via block timing]

key-files:
  created: []
  modified:
    - src/dental_notes/session/manager.py
    - tests/test_session_manager.py
    - tests/conftest.py

key-decisions:
  - "Rolling buffer cleared at START of auto-pause entry (not resume) to prevent replay of already-transcribed audio"
  - "3 consecutive speech blocks (300ms) required to confirm resume from auto-pause"
  - "next_patient() does NOT trigger extraction -- extraction deferred to review for fast transitions"
  - "Mic disconnect detected via block arrival timing, not PortAudioError (USB disconnect may not raise immediately)"
  - "Whisper OOM retry saves raw audio as .npy to recovery_audio/ dir on exhaustion instead of crashing"
  - "Auto-save try/except prevents store failure from crashing the processing loop"

patterns-established:
  - "_vad_override injection: set before start() to use FakeVadDetector instead of real VAD in tests"
  - "OOM retry with raw audio fallback: _transcribe_with_retry wraps transcribe with cache clearing and .npy save"
  - "Block timing for device disconnect: monotonic clock comparison instead of PortAudio error detection"

requirements-completed: [WRK-01, WRK-02, WRK-03]

# Metrics
duration: 12min
completed: 2026-03-30
---

# Phase 5 Plan 02: Session Manager Auto-Pause and Multi-Patient Batch Summary

**SessionManager extended with AUTO_PAUSED state machine, rolling audio buffer, next-patient batch flow, periodic auto-save, mic disconnect detection, and Whisper GPU OOM retry with raw audio fallback**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-30T00:59:29Z
- **Completed:** 2026-03-30T01:12:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- AUTO_PAUSED state with silence-triggered entry, speech-confirmed resume, and rolling buffer replay into chunker
- next_patient() batch flow: stop current session, save via SessionStore (RECORDED, no extraction), start new recording immediately
- Periodic auto-save writes _incomplete_ session files every N chunks or M seconds for crash recovery
- Mic disconnect detection via block arrival timing (configurable timeout) with auto-save and IDLE transition
- Whisper GPU OOM retry: up to 3 attempts with torch.cuda.empty_cache() and exponential backoff, raw audio saved as .npy on exhaustion
- 25 new tests across 6 test classes (436 total, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: AUTO_PAUSED state, rolling buffer, silence tracking, and auto-pause transitions** - `91fb0ed` (test)
2. **Task 2: Next Patient flow, periodic auto-save, mic disconnect handling, and Whisper GPU OOM retry** - `faa3c18` (feat)

_Both tasks used TDD: tests written first (RED), then implementation (GREEN)._

## Files Created/Modified
- `src/dental_notes/session/manager.py` - Extended SessionManager with AUTO_PAUSED state, rolling buffer, next_patient(), auto-save, mic disconnect, Whisper OOM retry
- `tests/test_session_manager.py` - 25 new tests: TestAutoPause (8), TestRollingBuffer (3), TestNextPatient (6), TestAutoSave (2), TestMicDisconnect (2), TestWhisperOomRetry (4)
- `tests/conftest.py` - FakeVadDetector for controllable VAD testing, FakeAudioCapture.add_blocks(), FakeSessionManager updated for AUTO_PAUSED

## Decisions Made
- Rolling buffer cleared at START of auto-pause entry to prevent replay of already-transcribed pre-silence audio (per research pitfall #1)
- 3 consecutive speech blocks (300ms at 100ms/block) required to confirm resume -- avoids spurious wake on noise spikes
- next_patient() does NOT trigger extraction -- per locked decision, extraction happens during review for fast patient transitions
- Mic disconnect detected via block arrival timing rather than PortAudioError (per research pitfall #6 -- USB disconnect may not raise immediately)
- _transcribe_with_retry saves raw audio as .npy instead of crashing -- preserves audio for later manual recovery
- Auto-save try/except wraps store calls to prevent disk errors from killing the processing loop

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing SessionState import in test_auto_save_does_not_crash_on_store_failure**
- **Found during:** Task 2 (TDD GREEN phase)
- **Issue:** Test referenced SessionState without importing it from the module
- **Fix:** Added `from dental_notes.session.manager import SessionManager, SessionState` import
- **Files modified:** tests/test_session_manager.py
- **Verification:** Test passes after fix
- **Committed in:** faa3c18 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial test import fix. No scope creep.

## Issues Encountered
None -- plan executed cleanly with TDD RED/GREEN for both tasks.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 6 SessionManager capabilities from plan objective delivered and tested
- Plan 05-03 (health dashboard routes) can build directly on these SessionManager methods
- auto_pause_enabled, rolling_buffer_secs, auto_save_interval_secs all configurable via Settings

## Self-Check: PASSED

All 3 modified files verified present. Both commits (91fb0ed, faa3c18) found in git log.

---
*Phase: 05-workflow-and-recovery*
*Completed: 2026-03-30*
