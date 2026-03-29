---
phase: 04-clinical-intelligence
plan: 03
subsystem: ui
tags: [htmx, jinja2, fastapi, template-selection, patient-summary, print-css, tab-ui, hotwords]

# Dependency graph
requires:
  - phase: 04-clinical-intelligence
    provides: "AppointmentType enum, PatientSummary model, TEMPLATE_HOTWORDS, TEMPLATE_OVERLAYS, template-aware ClinicalExtractor, format_patient_summary_for_clipboard"
provides:
  - "Template dropdown on review page with re-extraction on template change"
  - "Auto-detect as primary mechanism (no pre-recording dropdown)"
  - "TEMPLATE_HOTWORDS wired into SSE transcription loop via whisper_service.transcribe(hotwords=)"
  - "Tabbed review panel: Clinical Note / Patient Summary"
  - "Editable patient summary with save, copy, and print"
  - "Print-optimized patient summary page with @media print CSS"
  - "3-way speaker labels (Doctor/Patient/Assistant) in transcript display"
  - "Tab state preservation across HTMX re-extraction swaps"
affects: [05-batch-workflow, 06-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: [tab-ui-with-htmx-state-preservation, print-view-standalone-page, auto-detect-primary-manual-override]

key-files:
  created:
    - src/dental_notes/templates/_review_summary.html
    - src/dental_notes/templates/_print_summary.html
    - tests/test_review_routes.py
  modified:
    - src/dental_notes/ui/routes.py
    - src/dental_notes/templates/review.html
    - src/dental_notes/templates/index.html
    - src/dental_notes/templates/_session.html
    - src/dental_notes/static/style.css
    - src/dental_notes/static/review.js
    - tests/test_routes.py

key-decisions:
  - "Template selection moved from pre-recording dropdown to review page -- auto-detect is primary mechanism, manual override on review"
  - "Tab state preserved via data attribute on parent element, restored in htmx:afterSwap handler"
  - "Print summary is a standalone HTML page (not a partial) with its own print button and @media print CSS"

patterns-established:
  - "Auto-detect-primary: LLM auto-detects appointment type from transcript; user overrides only on review page if needed"
  - "Tab UI with HTMX: tab-btn/tab-content toggle with data-active-tab state preservation across HTMX swaps"
  - "Print view: standalone page with @media print CSS that hides controls and shows only content"

requirements-completed: [CLI-06, REV-04]

# Metrics
duration: 12min
completed: 2026-03-29
---

# Phase 4 Plan 03: Template UI, Patient Summary Tab, and Print View

**Template dropdown on review page with auto-detect as primary, tabbed patient summary with edit/save/print, hotwords wired into live SSE transcription, 3-way speaker labels -- 363 tests passing**

## Performance

- **Duration:** 12 min (including UX refactor after checkpoint feedback)
- **Started:** 2026-03-29T18:20:00Z
- **Completed:** 2026-03-29T21:25:00Z
- **Tasks:** 2 (Task 1: TDD implementation, Task 2: human-verify checkpoint)
- **Files modified:** 10

## Accomplishments
- Template dropdown on review page allowing manual override of auto-detected appointment type, with re-extraction on change
- Auto-detect as the primary mechanism: removed pre-recording dropdown, LLM infers type from transcript content
- TEMPLATE_HOTWORDS wired into SSE transcription loop for real-time accuracy boost during recording
- Tabbed review panel with Clinical Note and Patient Summary tabs, state preserved across HTMX swaps
- Editable patient summary with save, copy-to-clipboard, and print-to-browser-dialog functionality
- Print-optimized standalone page with @media print CSS (serif font, clean margins, no browser chrome)
- 3-way speaker labels (Doctor/Patient/Assistant) rendering in transcript panel
- Human verification of complete Phase 4 workflow approved

## Task Commits

Each task was committed atomically (TDD: test -> feat -> refactor):

1. **Task 1 (RED): Failing tests for template UI, patient summary, hotwords wiring** - `5a2193e` (test)
2. **Task 1 (GREEN): Template dropdown, patient summary tab, print view, hotwords wiring** - `57e36ec` (feat)
3. **UX refactor: Move template selection from recording to review stage** - `b55ca47` (refactor)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified
- `src/dental_notes/ui/routes.py` - Template-aware session routes, hotwords in SSE loop, patient summary save/print routes, re-extraction with template change
- `src/dental_notes/templates/review.html` - Tabbed review panel (Clinical Note / Patient Summary), template dropdown for override
- `src/dental_notes/templates/_review_summary.html` - Patient summary tab with editable textareas, save/copy/print buttons
- `src/dental_notes/templates/_print_summary.html` - Standalone print-optimized patient summary page
- `src/dental_notes/templates/index.html` - Recording page (pre-recording dropdown removed in refactor)
- `src/dental_notes/templates/_session.html` - Session display updates for template info
- `src/dental_notes/static/style.css` - Tab button/content styles, appointment type dropdown, @media print rules
- `src/dental_notes/static/review.js` - Tab switching, HTMX afterSwap state preservation, print/copy handlers
- `tests/test_review_routes.py` - New: tests for review page rendering, extract with template, save-summary, print-summary, 3-way speaker labels
- `tests/test_routes.py` - Extended: tests for session_start with appointment_type, session_stop template flow, SSE hotwords wiring

## Decisions Made
- **Template selection moved to review page** -- original plan had dropdown on recording page; after implementation, realized auto-detect is the better primary UX. Dropdown moved to review page for override only. This reduces cognitive load on the dentist before recording.
- **Tab state via data attribute** -- using `data-active-tab` attribute on a parent element, restored in `htmx:afterSwap` handler, avoids tab reset when re-extraction replaces panel content
- **Print summary as standalone page** -- not a CSS-only print of the review page; a dedicated route returns a clean, full HTML page optimized for printing with its own @media print rules

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UX refactor: removed pre-recording dropdown, made auto-detect primary**
- **Found during:** Post-Task-1 review (before human checkpoint)
- **Issue:** Original plan placed template dropdown on recording page before the Record button, adding unnecessary cognitive overhead. Auto-detection handles most cases correctly; manual selection is only needed as an override.
- **Fix:** Removed pre-recording dropdown from index.html, moved template selection to review page as an override mechanism. Auto-detect is now the primary flow.
- **Files modified:** src/dental_notes/templates/index.html, src/dental_notes/templates/review.html, src/dental_notes/ui/routes.py, tests/test_routes.py
- **Verification:** All 363 tests pass. Human verification approved the refined UX.
- **Committed in:** b55ca47

---

**Total deviations:** 1 auto-fixed (UX improvement)
**Impact on plan:** Better user experience. No scope creep -- same features, better flow.

## Issues Encountered
None -- plan executed smoothly with one UX refinement.

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- Phase 4 (Clinical Intelligence) is now complete: all 3 plans done, all 4 requirements (CLI-05, CLI-06, CLI-07, REV-04) verified
- 363 tests passing across all modules
- Ready to proceed to Phase 5: Workflow and Recovery (batch multi-patient day mode, auto-pause, error recovery, health monitoring)
- CUDA version survey on operatory PCs still needed before Phase 6 (noted in STATE.md blockers)

## Self-Check: PASSED

All 10 files verified present. All 3 task commits (5a2193e, 57e36ec, b55ca47) verified in git log.
363 tests passing (15 new in test_review_routes.py + extensions to test_routes.py).

---
*Phase: 04-clinical-intelligence*
*Completed: 2026-03-29*
