---
phase: 3
slug: review-and-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.2.0 + pytest-asyncio >=0.23.0 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/ -x --tb=short` |
| **Full suite command** | `pytest tests/ --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x --tb=short`
- **After every plan wave:** Run `pytest tests/ --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | REV-01 | unit (route) | `pytest tests/test_review_routes.py::test_review_page_renders_transcript_and_note -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | REV-02 | unit (route) | `pytest tests/test_review_routes.py::test_save_edits_persists_to_session -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | REV-03 | unit (formatter) | `pytest tests/test_note_formatter.py::test_format_note_for_clipboard -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | AUD-02 | unit | `pytest tests/test_session_store.py::test_finalize_deletes_transcript -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | REV-01 | integration | `pytest tests/test_review_routes.py::test_review_has_two_panels -x` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | AUD-02 | unit | `pytest tests/test_session_store.py::test_finalize_missing_file_succeeds -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_session_store.py` — covers session persistence (create, load, list, update, delete, finalize)
- [ ] `tests/test_review_routes.py` — covers review page routes (render, save edits, extract, finalize, session list)
- [ ] `tests/test_note_formatter.py` — covers clipboard text formatting (Copy All output, per-section copy)
- [ ] Update `tests/conftest.py` — add FakeSessionStore, sample SavedSession fixtures

*Existing test infrastructure (182+ tests, conftest.py fakes, httpx AsyncClient pattern) covers the testing foundation. New test files needed for Phase 3 features.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Side-by-side layout renders correctly in browser | REV-01 | CSS layout visual verification | Open review page, verify 50/50 split with independent scroll |
| Clipboard copy works in browser | REV-03 | Browser API requires user gesture | Click Copy All, paste into text editor, verify formatting |
| Dictation on editable fields | REV-02 | Requires mic hardware + Whisper | Focus a textarea, activate mic, speak, verify text appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
