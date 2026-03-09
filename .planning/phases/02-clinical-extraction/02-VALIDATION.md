---
phase: 2
slug: clinical-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `cd ~/claude/dental-notes && python3 -m pytest tests/ -x --tb=short -q` |
| **Full suite command** | `cd ~/claude/dental-notes && python3 -m pytest tests/ --tb=short -v` |
| **Integration command** | `cd ~/claude/dental-notes && python3 -m pytest tests/test_clinical_integration.py --integration -x --tb=short -v` |
| **Estimated runtime** | ~10 seconds (unit), ~2 minutes (integration with Ollama) |

---

## Sampling Rate

- **After every task commit:** Run `cd ~/claude/dental-notes && python3 -m pytest tests/ -x --tb=short -q`
- **After every plan wave:** Run `cd ~/claude/dental-notes && python3 -m pytest tests/ --tb=short -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Test File | Status |
|---------|------|------|-------------|-----------|-------------------|-----------|--------|
| 02-01-T1 | 01 | 1 | CLI-01, CLI-02, CLI-03 | unit | `pytest tests/test_clinical_models.py -x --tb=short` | tests/test_clinical_models.py | pending |
| 02-01-T2 | 01 | 1 | CLI-01, CLI-04 | unit | `pytest tests/test_ollama_service.py -x --tb=short` | tests/test_ollama_service.py | pending |
| 02-02-T1 | 02 | 2 | CLI-01, CLI-02, CLI-03 | unit | `pytest tests/test_extractor.py -x --tb=short` | tests/test_extractor.py | pending |
| 02-02-T2 | 02 | 2 | CLI-04 | unit | `pytest tests/test_speaker_reattribution.py -x --tb=short` | tests/test_speaker_reattribution.py | pending |
| 02-03-T1 | 03 | 3 | ALL | integration | `pytest tests/test_clinical_integration.py --integration -x --tb=short` | tests/test_clinical_integration.py | pending |
| 02-03-T2 | 03 | 3 | ALL | checkpoint | Human verification with real Ollama + transcript | N/A | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_clinical_models.py` — Pydantic model validation tests (SoapNote, CdtCode, ExtractionResult)
- [ ] `tests/test_ollama_service.py` — OllamaService unit tests (health check, structured output, unload)
- [ ] `tests/test_extractor.py` — ClinicalExtractor unit tests (extraction, GPU handoff)
- [ ] `tests/test_speaker_reattribution.py` — SpeakerReattributor unit tests
- [ ] `tests/test_clinical_integration.py` — End-to-end integration test (requires Ollama)
- [ ] Ollama must be installed and Qwen3 model pulled on test machine for integration tests

*Note: Unit tests must work without a running Ollama instance (use FakeOllamaService). Integration tests require Ollama.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SOAP note quality from real dental transcript | CLI-01, CLI-02 | LLM output quality is subjective | Process a real transcript, review SOAP note for clinical accuracy |
| CDT code accuracy | CLI-03 | Requires dental domain expertise | Verify suggested codes match procedures discussed |
| Speaker re-attribution accuracy | CLI-04 | Contextual judgment | Compare re-attributed labels against known speaker turns |
| GPU memory usage during LLM inference | PRV-01 | Hardware-dependent | Run nvidia-smi during Ollama inference |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
