---
phase: 03-review-and-export
plan: 02
subsystem: ui, routes
tags: [fastapi, htmx, jinja2, clipboard-api, css-grid, review-workflow]

# Dependency graph
requires:
  - phase: 03-review-and-export
    provides: SessionStore, SavedSession, NoteFormatter, enriched SoapNote
  - phase: 02-clinical-extraction
    provides: ClinicalExtractor, ExtractionResult, OllamaService
provides:
  - Review page with 50/50 side-by-side transcript/SOAP note layout
  - Session list with status badges (Recorded/Extracted/Reviewed)
  - Auto-extract SOAP note on session stop with GPU handoff
  - Save/finalize/regenerate routes for review workflow
  - Clipboard copy (Copy All + per-section) via server-side formatting
  - Transcript dirty tracking with regeneration banner
  - Note-text API for server-side clipboard formatting
affects: [03-03 dictation on editable fields]

# Tech tracking
tech-stack:
  added: []
  patterns: [css-grid-50-50-layout, htmx-partial-swap-for-extraction, hx-redirect-after-stop, thread-pool-extraction, transcript-dirty-tracking]

key-files:
  created:
    - src/dental_notes/templates/review.html
    - src/dental_notes/templates/_review_note.html
    - src/dental_notes/templates/_review_transcript.html
    - src/dental_notes/templates/_session_list.html
    - src/dental_notes/templates/sessions.html
    - src/dental_notes/static/review.js
    - tests/test_review_routes.py
  modified:
    - src/dental_notes/ui/routes.py
    - src/dental_notes/main.py
    - src/dental_notes/static/style.css
    - src/dental_notes/templates/index.html
    - tests/test_routes.py

key-decisions:
  - "Session stop now auto-extracts and redirects to review via HX-Redirect (breaking change from old stop behavior)"
  - "Extraction runs in thread pool via run_in_executor to avoid blocking asyncio event loop"
  - "Server-side note formatting via /api/session/{id}/note-text avoids duplicating formatter logic in JavaScript"
  - "Clipboard fallback using hidden textarea + execCommand for non-secure contexts"
  - "Review page uses full viewport width (no max-width) for 50/50 panel split"
  - "Transcript parsed back to chunks via _parse_transcript_text helper on save"

patterns-established:
  - "HX-Redirect pattern: return empty body with HX-Redirect header for post-action navigation"
  - "Thread pool extraction: async routes use run_in_executor for blocking LLM calls"
  - "HTMX partial swap: extraction returns _review_note.html partial for #note-panel swap"
  - "Dirty tracking: JavaScript stores original value on load, compares on input"

requirements-completed: [REV-01, REV-02, REV-03, AUD-02]

# Metrics
duration: 8min
completed: 2026-03-10
---

# Phase 3 Plan 02: Review UI Summary

**Side-by-side review page with editable SOAP note, clipboard copy, session list with status badges, and auto-extraction on session stop**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-10T04:49:06Z
- **Completed:** 2026-03-10T04:57:57Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Review page with 50/50 CSS Grid layout: transcript left, SOAP note right, both independently scrollable
- All SOAP sections (Subjective, Objective, Assessment, Plan, CDT Codes, Clinical Discussion, Medications, VA Narrative) editable via textareas
- Copy All fetches server-formatted text, per-section copy reads from textarea with section header
- Session stop auto-extracts SOAP note via GPU handoff and redirects to review page
- Session list with timestamp, transcript preview, and colored status badges (gray/blue/green)
- Transcript dirty tracking shows "Transcript changed -- Regenerate note?" banner
- Finalize & Clear with hx-confirm deletes transcript and shows confirmation with navigation links
- 246 tests passing (20 new review + 228 existing - 2 updated), 0 broken

## Task Commits

Each task was committed atomically (TDD: test -> feat for Task 1):

1. **Task 1: Review and session list routes with tests**
   - `2600554` (test) - failing tests for review workflow routes
   - `02ead79` (feat) - review routes, templates, updated main.py lifespan
2. **Task 2: Review templates, session list UI, and JavaScript**
   - `d09723e` (feat) - review.js, style.css, full template UI

## Files Created/Modified
- `src/dental_notes/ui/routes.py` - Added 7 review routes (review, extract, save, finalize, sessions, note-text) + modified stop route for auto-extract + redirect
- `src/dental_notes/main.py` - Lifespan now initializes SessionStore, OllamaService, ClinicalExtractor
- `src/dental_notes/templates/review.html` - Full review page with 50/50 grid, HTMX extraction, action bar
- `src/dental_notes/templates/_review_note.html` - SOAP note partial with editable textareas for all sections
- `src/dental_notes/templates/_review_transcript.html` - Transcript textarea partial with dirty tracking
- `src/dental_notes/templates/_session_list.html` - Session card list with timestamp, preview, status badges
- `src/dental_notes/templates/sessions.html` - Standalone session list page
- `src/dental_notes/templates/index.html` - Added session list section below transcript
- `src/dental_notes/static/review.js` - Clipboard copy (Copy All + per-section), dirty tracking, auto-resize
- `src/dental_notes/static/style.css` - Review grid layout, panel styles, status badges, regen banner, finalize confirmation
- `tests/test_review_routes.py` - 20 tests for all review workflow routes
- `tests/test_routes.py` - Updated 2 tests for new stop route behavior (HX-Redirect + session creation)

## Decisions Made
- Session stop route changed from returning HTML with transcript path to auto-extracting and returning HX-Redirect -- this is a breaking change from Phase 1 behavior but required by the plan
- Server-side note formatting via dedicated API endpoint avoids duplicating the formatter logic in JavaScript
- Clipboard uses navigator.clipboard.writeText with fallback to execCommand for non-secure contexts
- Review page uses full viewport width (removes max-width: 900px from body) to give 50/50 panels adequate space
- Transcript text parsed back to (speaker, text) chunks on save using best-effort regex parsing
- ClinicalExtractor initialization in lifespan wrapped in try/except so server starts even without Ollama

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing route tests for new stop behavior**
- **Found during:** Task 1
- **Issue:** Two existing tests (test_stop_shows_transcript_path, test_stop_preserves_transcript_with_speaker_labels) expected the old stop behavior (returning HTML with transcript) but stop now returns HX-Redirect
- **Fix:** Updated tests to verify HX-Redirect header and session creation in store
- **Files modified:** tests/test_routes.py
- **Verification:** All 246 tests pass
- **Committed in:** 02ead79

**2. [Rule 2 - Missing Critical] Added session_store to existing test_app fixture**
- **Found during:** Task 1
- **Issue:** Existing test_app fixture in test_routes.py didn't set session_store on app.state, causing index route to fail
- **Fix:** Added fake_session_store and clinical_extractor to test_app fixture
- **Files modified:** tests/test_routes.py
- **Verification:** All existing route tests continue to pass
- **Committed in:** 02ead79

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness -- existing tests needed updating for the intentional stop route behavior change. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Review UI fully functional with all SOAP editing, copy, and finalization
- Ready for Plan 03-03: dictation on editable fields + human verification checkpoint
- All backend contracts (routes, templates, JavaScript) established
- 246 tests passing as regression baseline

## Self-Check: PASSED

- All 12 claimed files exist on disk
- All 3 commit hashes verified in git log
- review.html: 93 lines (min 50)
- review.js: 174 lines (min 40)
- _session_list.html: 23 lines (min 15)
- test_review_routes.py: 333 lines (min 100)
- 246 tests passing, 13 skipped (integration), 0 failures

---
*Phase: 03-review-and-export*
*Completed: 2026-03-10*
