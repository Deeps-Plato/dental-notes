---
phase: 02-clinical-extraction
plan: 01
subsystem: clinical
tags: [pydantic, ollama, soap-note, cdt-codes, structured-output]

# Dependency graph
requires:
  - phase: 01-streaming-capture
    provides: "SessionManager with transcript chunks, WhisperService, config.py Settings"
provides:
  - "SoapNote, CdtCode, SpeakerChunk, ExtractionResult Pydantic models"
  - "OllamaService with health check, structured generation, and model unloading"
  - "FakeOllamaService for downstream unit tests"
  - "EXTRACTION_SYSTEM_PROMPT with dental SOAP instructions and CDT reference"
  - "Settings extended with 5 Ollama configuration fields"
affects: [02-02-PLAN, 02-03-PLAN]

# Tech tracking
tech-stack:
  added: [ollama>=0.6.1]
  patterns: [Pydantic structured output via Ollama format parameter, /nothink prefix for Qwen3, keep_alive=0 for GPU memory release]

key-files:
  created:
    - src/dental_notes/clinical/__init__.py
    - src/dental_notes/clinical/models.py
    - src/dental_notes/clinical/prompts.py
    - src/dental_notes/clinical/ollama_service.py
    - tests/test_clinical_models.py
    - tests/test_ollama_service.py
  modified:
    - src/dental_notes/config.py
    - pyproject.toml
    - tests/conftest.py

key-decisions:
  - "CDT reference embedded as string constant in prompts.py (45 common codes) rather than external file"
  - "FakeOllamaService nests cdt_codes inside soap_note matching ExtractionResult schema"
  - "OllamaService uses ollama.Client sync API (not async) for simplicity"
  - "/nothink prefix prepended to all user content to disable Qwen3 thinking mode"

patterns-established:
  - "Clinical module pattern: src/dental_notes/clinical/ with models, prompts, and service modules"
  - "Fake service pattern: FakeOllamaService in conftest.py records calls and returns schema-valid JSON"
  - "TDD pattern continued: test file written first (RED), then implementation (GREEN)"

requirements-completed: [CLI-01, CLI-02, CLI-03, CLI-04]

# Metrics
duration: 6min
completed: 2026-03-09
---

# Phase 2 Plan 01: Clinical Foundation Summary

**Pydantic SOAP note models, Ollama service wrapper with health checks and structured generation, 45-code CDT reference prompt, and FakeOllamaService test double**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-09T06:13:46Z
- **Completed:** 2026-03-09T06:20:15Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- SoapNote, CdtCode, SpeakerChunk, ExtractionResult Pydantic models with JSON schema generation for Ollama structured output
- OllamaService wrapping ollama.Client with is_available, is_model_ready, generate_structured, and unload methods
- EXTRACTION_SYSTEM_PROMPT with dental SOAP instructions, speaker attribution rules, and 45-code CDT reference
- FakeOllamaService in conftest.py with call recording and schema-valid default response
- Settings extended with 5 Ollama configuration fields (host, model, fallback_model, temperature, num_ctx)
- 40 new tests (25 model + 15 service), full suite at 156 tests with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic models, config extension, and prompts module** - `7591908` (feat)
2. **Task 2: OllamaService with health check, structured generation, and model unloading** - `712433e` (feat)

_Note: TDD tasks -- tests written first (RED), then implementation (GREEN) in same commit._

## Files Created/Modified
- `src/dental_notes/clinical/__init__.py` - Empty module init
- `src/dental_notes/clinical/models.py` - CdtCode, SpeakerChunk, SoapNote, ExtractionResult Pydantic models
- `src/dental_notes/clinical/prompts.py` - CDT_REFERENCE (45 codes), EXTRACTION_SYSTEM_PROMPT
- `src/dental_notes/clinical/ollama_service.py` - OllamaService with health checks, structured generation, model unloading
- `src/dental_notes/config.py` - Extended Settings with 5 Ollama fields
- `pyproject.toml` - Added ollama>=0.6.1 dependency
- `tests/test_clinical_models.py` - 25 tests for models, config, and prompts
- `tests/test_ollama_service.py` - 15 tests for OllamaService and FakeOllamaService
- `tests/conftest.py` - Added FakeOllamaService class and fake_ollama_service fixture

## Decisions Made
- Embedded CDT reference as string constant in prompts.py (45 common codes) rather than external JSON file -- keeps the prompt self-contained and avoids file I/O during LLM calls
- FakeOllamaService default response_data nests cdt_codes inside soap_note (matching ExtractionResult/SoapNote schema hierarchy) -- critical for downstream Pydantic validation
- OllamaService uses ollama.Client sync API (not async) -- dental extraction is a single blocking call after transcription completes, no concurrency benefit from async
- /nothink prefix prepended to all user content in generate_structured -- disables Qwen3 thinking mode for faster, more deterministic structured output

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Ollama installation is a prerequisite documented in project requirements but not configured here.

## Next Phase Readiness
- clinical/ module with models, prompts, and OllamaService ready for Plan 02 (ClinicalExtractor and SpeakerReattributor)
- FakeOllamaService available in conftest.py for Plan 02 unit tests
- All contracts (Pydantic models, service interface, prompt constants) established and tested
- No blockers

---
*Phase: 02-clinical-extraction*
*Completed: 2026-03-09*
