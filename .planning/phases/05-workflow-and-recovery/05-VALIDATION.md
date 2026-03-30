---
phase: 5
slug: workflow-and-recovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.2.0 + pytest-asyncio >=0.23.0 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
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
| 05-01-01 | 01 | 1 | WRK-01 | unit | `pytest tests/test_session_manager.py::TestNextPatient -x` | No -- Wave 0 | ⬜ pending |
| 05-01-02 | 01 | 1 | WRK-01 | unit | `pytest tests/test_session_store.py::TestSessionListFiltering -x` | No -- Wave 0 | ⬜ pending |
| 05-01-03 | 01 | 1 | WRK-01 | unit | `pytest tests/test_routes.py::TestNextPatientRoute -x` | No -- Wave 0 | ⬜ pending |
| 05-02-01 | 02 | 1 | WRK-02 | unit | `pytest tests/test_session_manager.py::TestAutoPause -x` | No -- Wave 0 | ⬜ pending |
| 05-02-02 | 02 | 1 | WRK-02 | unit | `pytest tests/test_session_manager.py::TestRollingBuffer -x` | No -- Wave 0 | ⬜ pending |
| 05-02-03 | 02 | 1 | WRK-02 | unit | `pytest tests/test_routes.py::TestAutoPauseSSE -x` | No -- Wave 0 | ⬜ pending |
| 05-03-01 | 03 | 2 | WRK-03 | unit | `pytest tests/test_extractor.py::TestExtractionRetry -x` | No -- Wave 0 | ⬜ pending |
| 05-03-02 | 03 | 2 | WRK-03 | unit | `pytest tests/test_session_manager.py::TestAutoSave -x` | No -- Wave 0 | ⬜ pending |
| 05-03-03 | 03 | 2 | WRK-03 | unit | `pytest tests/test_session_store.py::TestIncompleteSessionRecovery -x` | No -- Wave 0 | ⬜ pending |
| 05-03-04 | 03 | 2 | WRK-03 | unit | `pytest tests/test_session_manager.py::TestMicDisconnect -x` | No -- Wave 0 | ⬜ pending |
| 05-04-01 | 04 | 2 | WRK-04 | unit | `pytest tests/test_health.py -x` | No -- Wave 0 | ⬜ pending |
| 05-04-02 | 04 | 2 | WRK-04 | unit | `pytest tests/test_routes.py::TestHealthStatusBar -x` | No -- Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_health.py` — stubs for WRK-04 (HealthChecker unit tests)
- [ ] `tests/test_session_manager.py::TestAutoPause` — stubs for WRK-02 (auto-pause state transitions)
- [ ] `tests/test_session_manager.py::TestRollingBuffer` — stubs for WRK-02 (buffer replay)
- [ ] `tests/test_session_manager.py::TestNextPatient` — stubs for WRK-01 (next patient flow)
- [ ] `tests/test_session_manager.py::TestAutoSave` — stubs for WRK-03 (periodic save)
- [ ] `tests/test_session_manager.py::TestMicDisconnect` — stubs for WRK-03 (mic error handling)
- [ ] `tests/test_session_store.py::TestSessionListFiltering` — stubs for WRK-01 (date/status filter)
- [ ] `tests/test_session_store.py::TestIncompleteSessionRecovery` — stubs for WRK-03 (crash recovery)
- [ ] `tests/test_extractor.py::TestExtractionRetry` — stubs for WRK-03 (retry with tenacity)
- [ ] `tests/test_routes.py::TestNextPatientRoute` — stubs for WRK-01 (route test)
- [ ] `tests/test_routes.py::TestHealthStatusBar` — stubs for WRK-04 (HTMX polling test)
- [ ] `tests/conftest.py` — extend FakeSessionManager with AUTO_PAUSED state

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rolling buffer captures first words on speech resume | WRK-02 | Real mic + real silence gap needed | Record silence for 30+ seconds, resume speaking, verify first words appear in transcript |
| Mic disconnect triggers auto-save | WRK-03 | Physical USB disconnect needed | Start recording, unplug mic, verify transcript saved and alert shown |
| Health check detects real GPU/Ollama/mic status | WRK-04 | Requires real hardware | Stop Ollama, verify /api/health shows it as unhealthy, restart and verify recovery |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
