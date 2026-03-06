---
phase: 1
slug: streaming-capture-and-transcription
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.2.0 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] (Wave 0 creates) |
| **Quick run command** | `pytest tests/ -x --tb=short` |
| **Full suite command** | `pytest tests/ --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x --tb=short`
- **After every plan wave:** Run `pytest tests/ --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | - | unit | `pytest tests/ -x --tb=short` | Wave 0 | pending |
| 1-02-01 | 02 | 1 | AUD-01 | unit | `pytest tests/test_session_manager.py -x` | Wave 0 | pending |
| 1-02-02 | 02 | 1 | TRX-01 | unit | `pytest tests/test_whisper_service.py -x` | Wave 0 | pending |
| 1-02-03 | 02 | 1 | TRX-02 | unit | `pytest tests/test_whisper_service.py::test_dental_prompt -x` | Wave 0 | pending |
| 1-02-04 | 02 | 1 | PRV-01 | unit | `pytest tests/test_session_manager.py::test_no_network -x` | Wave 0 | pending |
| 1-02-05 | 02 | 1 | - | unit | `pytest tests/test_vad.py -x` | Wave 0 | pending |
| 1-02-06 | 02 | 1 | - | unit | `pytest tests/test_stitcher.py -x` | Wave 0 | pending |
| 1-02-07 | 02 | 1 | - | unit | `pytest tests/test_transcript_writer.py -x` | Wave 0 | pending |
| 1-02-08 | 02 | 1 | - | integration | `pytest tests/test_routes.py -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — v2 project setup with pytest config, dependencies
- [ ] `tests/conftest.py` — shared fixtures: mock audio arrays, fake VAD model, test config
- [ ] `tests/test_session_manager.py` — covers AUD-01, PRV-01
- [ ] `tests/test_whisper_service.py` — covers TRX-01, TRX-02
- [ ] `tests/test_vad.py` — VAD speech detection
- [ ] `tests/test_chunker.py` — chunk boundary logic
- [ ] `tests/test_stitcher.py` — overlap deduplication
- [ ] `tests/test_transcript_writer.py` — file writing, crash safety
- [ ] `tests/test_routes.py` — SSE endpoint integration
- [ ] Framework install: `pip install pytest pytest-cov pytest-asyncio httpx ruff mypy`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Audio level indicator visible in UI | AUD-01 | Visual UI element | Start session, verify level meter responds to speech |
| Mic selection dropdown populated | AUD-01 | Requires real audio hardware | Open UI, verify mic list shows connected devices |
| Keyboard shortcut works with Dentrix focus | - | Requires Dentrix running | Press F9 with Dentrix in foreground, verify session starts |
| GTX 1050 VRAM stays under 4GB | TRX-01 | Requires target GPU hardware | Run `nvidia-smi` during active session on GTX 1050 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
