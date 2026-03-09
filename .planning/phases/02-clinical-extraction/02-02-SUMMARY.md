---
phase: 02-clinical-extraction
plan: 02
subsystem: clinical
tags: [ollama, pydantic, soap-note, cdt-codes, speaker-attribution, gpu-handoff, tdd]

# Dependency graph
requires:
  - phase: 02-clinical-extraction/01
    provides: "Pydantic models (ExtractionResult, SoapNote, SpeakerChunk, CdtCode), OllamaService, EXTRACTION_SYSTEM_PROMPT, FakeOllamaService"
provides:
  - "ClinicalExtractor: transcript -> ExtractionResult (SOAP note + CDT codes + speaker chunks)"
  - "ClinicalExtractor.extract_with_gpu_handoff(): Whisper unload -> LLM -> LLM unload -> Whisper reload"
  - "SpeakerReattributor: LLM-based speaker label correction preserving chunk boundaries"
  - "FakeWhisperServiceGpu: GPU handoff test double with unload/load tracking"
  - "SAMPLE_DENTAL_TRANSCRIPT: shared fixture for extraction tests"
affects: [02-clinical-extraction/03, 03-review-export]

# Tech tracking
tech-stack:
  added: []
  patterns: ["GPU handoff with finally-block safety", "Pydantic wrapper model for structured LLM array output", "TDD RED-GREEN with separate commits"]

key-files:
  created:
    - src/dental_notes/clinical/extractor.py
    - src/dental_notes/clinical/speaker.py
    - tests/test_extractor.py
    - tests/test_speaker_reattribution.py
  modified:
    - tests/conftest.py

key-decisions:
  - "FakeWhisperServiceGpu as separate class from FakeWhisperService to avoid breaking existing 156 tests"
  - "FakeOllamaService enhanced with unload_count tracking (backward compatible)"
  - "SpeakerReattributor uses _SpeakerChunkList wrapper model for Pydantic structured output schema"
  - "Speaker system prompt separate from EXTRACTION_SYSTEM_PROMPT (focused on attribution only)"

patterns-established:
  - "GPU handoff pattern: whisper.unload() -> extract() -> finally { ollama.unload(); whisper.load_model() }"
  - "Pydantic wrapper model for array outputs: _SpeakerChunkList wraps list[SpeakerChunk] for LLM schema"
  - "FakeWhisperServiceGpu for GPU memory management tests (separate from transcription FakeWhisperService)"

requirements-completed: [CLI-01, CLI-02, CLI-03, CLI-04]

# Metrics
duration: 7min
completed: 2026-03-09
---

# Phase 2 Plan 02: Clinical Extraction Pipeline Summary

**ClinicalExtractor (transcript -> SOAP note + CDT codes) and SpeakerReattributor (LLM speaker correction) with GPU handoff for 4GB VRAM hardware**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-09T06:23:55Z
- **Completed:** 2026-03-09T06:31:36Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- ClinicalExtractor converts dental transcripts to structured ExtractionResult (SOAP note + CDT codes + speaker chunks) via OllamaService
- GPU handoff method (extract_with_gpu_handoff) safely sequences Whisper unload -> LLM inference -> LLM unload -> Whisper reload with finally-block guarantee
- SpeakerReattributor corrects keyword-based speaker labels using LLM conversational context analysis while preserving chunk boundaries
- 26 new tests (17 extractor + 9 speaker), 182 total suite passing with zero regressions

## Task Commits

Each task was committed atomically (TDD RED then GREEN):

1. **Task 1: ClinicalExtractor** - `fb54bf1` (test: failing tests) -> `351c424` (feat: implementation)
2. **Task 2: SpeakerReattributor** - `4daf854` (test: failing tests) -> `ede7875` (feat: implementation)

_TDD: Each task had separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `src/dental_notes/clinical/extractor.py` - ClinicalExtractor with extract(), extract_from_chunks(), extract_with_gpu_handoff()
- `src/dental_notes/clinical/speaker.py` - SpeakerReattributor with reattribute() and SPEAKER_SYSTEM_PROMPT
- `tests/test_extractor.py` - 17 tests for extraction pipeline and GPU handoff
- `tests/test_speaker_reattribution.py` - 9 tests for speaker re-attribution
- `tests/conftest.py` - Added FakeWhisperServiceGpu, SAMPLE_DENTAL_TRANSCRIPT, unload_count on FakeOllamaService

## Decisions Made
- Created FakeWhisperServiceGpu as a separate class (not modifying existing FakeWhisperService) to avoid breaking 156 existing tests that depend on the current constructor signature
- Added unload_count tracking to FakeOllamaService (backward compatible -- existing tests not affected)
- Speaker system prompt is a separate constant in speaker.py (not reusing EXTRACTION_SYSTEM_PROMPT) because attribution-only context is shorter and more focused
- Used _SpeakerChunkList Pydantic wrapper model to provide structured output schema for LLM array responses

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FakeWhisperService kept as-is, new FakeWhisperServiceGpu created**
- **Found during:** Task 1 (conftest.py updates)
- **Issue:** Plan said to replace FakeWhisperService, but existing class has different constructor signature (responses param) used by 156 tests
- **Fix:** Created separate FakeWhisperServiceGpu class with GPU-tracking constructor, added fake_whisper_service fixture returning it
- **Files modified:** tests/conftest.py
- **Verification:** All 156 existing tests still pass, 26 new tests pass
- **Committed in:** fb54bf1 (Task 1 RED commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - backward compatibility)
**Impact on plan:** Minimal -- separate class name is cleaner than overloading existing fake.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ClinicalExtractor and SpeakerReattributor ready for integration testing in Plan 03
- Plan 03 will test with real Ollama + Qwen3 and includes human verification checkpoint
- GPU handoff verified with fakes; real hardware test deferred to Plan 03

## Self-Check: PASSED

- All 6 files verified present on disk
- All 4 task commits verified in git history (fb54bf1, 351c424, 4daf854, ede7875)
- 182 tests passing, 0 regressions

---
*Phase: 02-clinical-extraction*
*Completed: 2026-03-09*
