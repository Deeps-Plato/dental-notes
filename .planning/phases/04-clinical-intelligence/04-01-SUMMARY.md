---
phase: 04-clinical-intelligence
plan: 01
subsystem: transcription, clinical
tags: [whisper, vocabulary, hotwords, speaker-classification, llm-reattribution]

# Dependency graph
requires:
  - phase: 03-review-export
    provides: Working extraction pipeline with 2-role speaker classification
provides:
  - Expanded DENTAL_INITIAL_PROMPT with anesthetics, materials, pathology, anatomy terms
  - Custom vocab file loading (load_custom_vocab, build_initial_prompt)
  - TEMPLATE_HOTWORDS dict for 6 appointment types
  - WhisperService.transcribe() hotwords parameter
  - 3-way speaker classification (Doctor/Patient/Assistant) with assistant keyword patterns
  - 3-role SPEAKER_SYSTEM_PROMPT for LLM re-attribution
affects: [04-02, 04-03, phase-5]

# Tech tracking
tech-stack:
  added: []
  patterns: [template-hotwords-dict, custom-vocab-file-loading, 3-way-classification]

key-files:
  created:
    - src/dental_notes/transcription/vocab.py
    - tests/test_vocab.py
    - src/dental_notes/session/speaker.py
    - tests/test_speaker.py
  modified:
    - src/dental_notes/transcription/whisper_service.py
    - src/dental_notes/config.py
    - src/dental_notes/clinical/speaker.py
    - src/dental_notes/clinical/models.py
    - tests/test_whisper_service.py
    - tests/test_speaker_reattribution.py
    - tests/test_clinical_models.py

key-decisions:
  - "Doctor-wins-ties: when assistant and doctor scores are equal, classify as Doctor (locked decision)"
  - "Token budget: DENTAL_INITIAL_PROMPT covers all 4 categories within ~224 token estimate"
  - "Custom vocab loaded at WhisperService init via build_initial_prompt(), not at transcribe time"

patterns-established:
  - "vocab.py owns all vocabulary constants; whisper_service.py imports from it"
  - "3-way speaker scoring with explicit tie-breaking rules"
  - "TEMPLATE_HOTWORDS keyed by appointment type string for downstream template selection"

requirements-completed: [CLI-05, CLI-07]

# Metrics
duration: 10min
completed: 2026-03-29
---

# Phase 4 Plan 01: Vocabulary & Speaker Classification Summary

**Expanded Whisper dental vocabulary across 4 term categories with custom vocab support, and extended speaker classification to 3 roles (Doctor/Patient/Assistant) with LLM re-attribution**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-29T18:08:46Z
- **Completed:** 2026-03-29T18:19:19Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Expanded DENTAL_INITIAL_PROMPT with anesthetics (Lidocaine, Septocaine, Marcaine), materials (Herculite, Estelite, Paracore), pathology (radiolucency, periapical, dehiscence), and anatomy (CEJ, furcation, mandibular canal) while staying within ~224 token budget
- Created vocab.py module with custom vocab file loading, TEMPLATE_HOTWORDS for 6 appointment types, and build_initial_prompt() for merging base + custom terms
- Extended classify_speaker() to 3-way classification with _ASSISTANT_PATTERNS covering instrument calls, patient comfort, procedural assists, and charting/admin
- Updated SPEAKER_SYSTEM_PROMPT for 3-role LLM re-attribution and SpeakerChunk model to accept "Assistant"

## Task Commits

Each task was committed atomically:

1. **Task 1: Expand Whisper vocabulary, hotwords, and custom vocab** - `f561598` (feat) -- vocab.py, whisper_service.py, config.py, tests
2. **Task 2: Extend speaker classification to 3 roles** - `0756b8f` (feat) -- session/speaker.py, clinical/speaker.py, models.py, tests

_Note: Task 1 code was already committed in prior execution with label 04-02; Task 2 is a fresh commit._

## Files Created/Modified
- `src/dental_notes/transcription/vocab.py` - DENTAL_INITIAL_PROMPT, TEMPLATE_HOTWORDS, load_custom_vocab(), build_initial_prompt()
- `src/dental_notes/transcription/whisper_service.py` - Imports from vocab.py, hotwords parameter support
- `src/dental_notes/config.py` - custom_vocab_path setting
- `src/dental_notes/session/speaker.py` - 3-way classify_speaker() with _ASSISTANT_PATTERNS
- `src/dental_notes/clinical/speaker.py` - 3-role SPEAKER_SYSTEM_PROMPT
- `src/dental_notes/clinical/models.py` - SpeakerChunk.speaker description updated
- `tests/test_vocab.py` - 13 tests for vocab management
- `tests/test_whisper_service.py` - Updated + 3 new tests for hotwords
- `tests/test_speaker.py` - 20 tests for 3-way speaker classification
- `tests/test_speaker_reattribution.py` - Updated for 3-role prompt + 3 new tests
- `tests/test_clinical_models.py` - Added assistant speaker acceptance test

## Decisions Made
- Doctor-wins-ties: when assistant and doctor scores are equal, classify as Doctor (locked decision from context)
- Custom vocab loaded once at WhisperService init, not per-transcribe call (performance)
- DENTAL_INITIAL_PROMPT trimmed tooth numbering and removed some v1 terms (Invisalign, sleep apnea) to fit expanded categories within token budget

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 1 code already committed under prior 04-02 labels**
- **Found during:** Task 1
- **Issue:** Prior execution had committed vocab.py, whisper_service.py, config.py, and test changes under commits labeled `84b0acd` and `f561598` with `04-02` scope
- **Fix:** Verified existing code matches Task 1 requirements, accepted existing commits, proceeded to Task 2
- **Files modified:** None (already in place)
- **Verification:** All 24 vocab/whisper tests pass
- **Committed in:** f561598 (prior)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor -- Task 1 code was already implemented. No scope creep.

## Issues Encountered
None beyond the pre-existing commit situation for Task 1.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- vocab.py and TEMPLATE_HOTWORDS ready for Plan 02 (template-specific extraction)
- 3-way speaker classification feeds into Plan 03 (patient summary generation)
- 348 tests passing, no regressions

## Self-Check: PASSED

All 11 files found. Both commit hashes verified (f561598, 0756b8f). 348 tests passing.

---
*Phase: 04-clinical-intelligence*
*Completed: 2026-03-29*
