---
phase: 04-clinical-intelligence
plan: 02
subsystem: clinical
tags: [ollama, pydantic, prompt-engineering, template-composition, patient-summary, appointment-type]

# Dependency graph
requires:
  - phase: 03-review-export
    provides: "ClinicalExtractor, ExtractionResult, SoapNote, OllamaService, SessionStore, formatter"
provides:
  - "AppointmentType enum with 6 dental appointment types"
  - "PatientSummary model for plain-language patient handouts"
  - "TEMPLATE_OVERLAYS and compose_extraction_prompt() for template-aware extraction"
  - "APPOINTMENT_TYPE_CLASSIFICATION_PROMPT for auto-detection from transcript"
  - "PATIENT_SUMMARY_PROMPT at 6th-grade reading level with forbidden clinical jargon"
  - "Template-aware ClinicalExtractor.extract() with auto-detection fallback"
  - "Patient summary generation in GPU handoff window"
  - "OllamaService.generate() for plain-text LLM calls"
  - "SavedSession with appointment_type and patient_summary fields"
  - "format_patient_summary_for_clipboard() for plain-text handout"
affects: [04-03, 04-04, 05-batch-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns: [template-composition, multi-call-gpu-handoff, graceful-fallback-classification]

key-files:
  created:
    - tests/test_prompts.py
  modified:
    - src/dental_notes/clinical/models.py
    - src/dental_notes/clinical/prompts.py
    - src/dental_notes/clinical/extractor.py
    - src/dental_notes/clinical/formatter.py
    - src/dental_notes/clinical/ollama_service.py
    - src/dental_notes/session/store.py
    - tests/test_clinical_models.py
    - tests/test_extractor.py
    - tests/test_session_store.py
    - tests/test_note_formatter.py
    - tests/conftest.py

key-decisions:
  - "Template overlays are short (3-5 line) emphasis sections appended to base EXTRACTION_SYSTEM_PROMPT, not full prompt rewrites"
  - "Auto-detection uses plain-text generate() (not structured) for lightweight classification"
  - "Patient summary uses transcript as input (not SOAP note) to avoid clinical jargon bleed"
  - "Summary generation failure is graceful -- logs warning, leaves patient_summary None, SOAP extraction still succeeds"
  - "FakeOllamaService tracks structured vs text calls separately for correct multi-call indexing"

patterns-established:
  - "Template composition: base prompt + appended overlay (not Jinja2, not string replace)"
  - "Multi-call GPU handoff: classify -> extract -> summarize within single Whisper unload/reload window"
  - "Graceful fallback: auto-detection returns 'general' on any error or unrecognized value"
  - "Test fake multi-call: FakeOllamaService supports list[dict] response_data + text_response for multi-call scenarios"

requirements-completed: [CLI-06, REV-04]

# Metrics
duration: 9min
completed: 2026-03-29
---

# Phase 4 Plan 02: Templates, Auto-Detection, and Patient Summary

**Appointment-type template overlays with auto-detection from transcript, patient summary generation in GPU handoff, and session persistence for new fields -- 99 new tests, 348 total passing**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-29T18:09:07Z
- **Completed:** 2026-03-29T18:18:30Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- AppointmentType enum (6 values) with template-specific prompt overlays for 5 non-general appointment types, each under 500 chars
- Auto-detection of appointment type from transcript via lightweight LLM classification call, with graceful fallback to "general"
- Patient summary generation as second LLM call during GPU handoff window, using transcript (not SOAP) to avoid jargon bleed
- compose_extraction_prompt() returns base prompt for None/general, appends overlay for specific types
- SavedSession backward-compatible with appointment_type and patient_summary fields
- format_patient_summary_for_clipboard() produces plain-text patient handout with section headers

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Task 1: Models, prompts, template overlays** - `84b0acd` (test) -> `f561598` (feat)
2. **Task 2: Extraction pipeline, session store, formatter** - `ead7de9` (test) -> `d39944d` (feat)

## Files Created/Modified
- `src/dental_notes/clinical/models.py` - AppointmentType enum, PatientSummary model, ExtractionResult.patient_summary field
- `src/dental_notes/clinical/prompts.py` - TEMPLATE_OVERLAYS, compose_extraction_prompt(), APPOINTMENT_TYPE_CLASSIFICATION_PROMPT, PATIENT_SUMMARY_PROMPT
- `src/dental_notes/clinical/extractor.py` - Template-aware extract(), _infer_appointment_type(), _generate_patient_summary(), updated GPU handoff
- `src/dental_notes/clinical/formatter.py` - format_patient_summary_for_clipboard()
- `src/dental_notes/clinical/ollama_service.py` - generate() method for plain-text LLM calls
- `src/dental_notes/session/store.py` - appointment_type and patient_summary fields on SavedSession
- `tests/test_prompts.py` - New: 25 tests for template overlays, composition, prompts
- `tests/test_clinical_models.py` - Extended with AppointmentType, PatientSummary, backward compat tests
- `tests/test_extractor.py` - Extended with template-aware, auto-detect, patient summary, multi-call tests
- `tests/test_session_store.py` - Extended with new field tests and backward compat
- `tests/test_note_formatter.py` - Extended with patient summary formatter tests
- `tests/conftest.py` - FakeOllamaService with multi-call, generate(), separate call tracking

## Decisions Made
- Template overlays appended as short emphasis sections (3-5 lines) to base prompt, not full rewrites -- keeps prompts maintainable and avoids duplicating SOAP structure
- Used plain-text generate() for classification (not structured) since we only need a single word response
- Patient summary prompt uses transcript as input per the pitfall #4 research finding: SOAP note input causes jargon bleed into patient-facing text
- Summary generation wrapped in try/except: failure logs warning but does not block the SOAP extraction result
- FakeOllamaService structured call index calculated as `call_count - generate_call_count - 1` to correctly index multi-call response data when generate() calls are interleaved

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added OllamaService.generate() method**
- **Found during:** Task 2 (extraction pipeline implementation)
- **Issue:** OllamaService only had generate_structured() -- no plain-text generation for classification
- **Fix:** Added generate() method to OllamaService mirroring generate_structured() but without schema/format parameter
- **Files modified:** src/dental_notes/clinical/ollama_service.py
- **Verification:** Integration with _infer_appointment_type() works, all tests pass
- **Committed in:** d39944d (Task 2 commit)

**2. [Rule 1 - Bug] Fixed FakeOllamaService multi-call indexing**
- **Found during:** Task 2 (test execution)
- **Issue:** When generate() and generate_structured() calls are interleaved, list-based response_data indexing was off because call_count included both types
- **Fix:** Track generate_call_count separately, compute structured index as call_count - generate_call_count - 1
- **Files modified:** tests/conftest.py
- **Verification:** 3-call GPU handoff test (classify + SOAP + summary) passes correctly
- **Committed in:** d39944d (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correct operation. No scope creep.

## Issues Encountered
None -- plan executed smoothly after deviation fixes.

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- Template composition layer ready for UI integration (dropdown selection + re-extraction on template change)
- Patient summary ready for review page tab UI
- Auto-detection pipeline ready for integration with recording flow
- SavedSession fields ready for session list display (appointment type badge)

## Self-Check: PASSED

All 12 files verified present. All 4 task commits (84b0acd, f561598, ead7de9, d39944d) verified in git log.
348 tests passing (99 new + 249 existing).

---
*Phase: 04-clinical-intelligence*
*Completed: 2026-03-29*
