---
phase: 4
slug: clinical-intelligence
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2+ with pytest-asyncio 0.23+ |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/ -x -q --tb=short` |
| **Full suite command** | `pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | CLI-05 | unit | `pytest tests/test_whisper_service.py -x` | Exists (update) | ⬜ pending |
| 04-01-02 | 01 | 1 | CLI-05 | unit | `pytest tests/test_whisper_service.py::test_transcribe_accepts_hotwords -x` | Wave 0 | ⬜ pending |
| 04-01-03 | 01 | 1 | CLI-05 | unit | `pytest tests/test_vocab.py -x` | Wave 0 | ⬜ pending |
| 04-02-01 | 02 | 1 | CLI-06 | unit | `pytest tests/test_prompts.py -x` | Wave 0 | ⬜ pending |
| 04-02-02 | 02 | 1 | CLI-06 | unit | `pytest tests/test_clinical_models.py -x` | Exists (update) | ⬜ pending |
| 04-02-03 | 02 | 1 | CLI-06 | unit | `pytest tests/test_session_store.py -x` | Exists (update) | ⬜ pending |
| 04-02-04 | 02 | 1 | CLI-06 | unit | `pytest tests/test_extractor.py -x` | Exists (update) | ⬜ pending |
| 04-02-05 | 02 | 1 | CLI-06 | unit | `pytest tests/test_extractor.py::test_auto_detect_template -x` | Wave 0 | ⬜ pending |
| 04-01-04 | 01 | 1 | CLI-07 | unit | `pytest tests/test_speaker.py -x` | Exists (update) | ⬜ pending |
| 04-01-05 | 01 | 1 | CLI-07 | unit | `pytest tests/test_speaker.py::test_assistant_doctor_tie_defaults_doctor -x` | Wave 0 | ⬜ pending |
| 04-01-06 | 01 | 1 | CLI-07 | unit | `pytest tests/test_speaker_reattribution.py -x` | Exists (update) | ⬜ pending |
| 04-01-07 | 01 | 1 | CLI-07 | unit | `pytest tests/test_clinical_models.py -x` | Exists (update) | ⬜ pending |
| 04-02-06 | 02 | 1 | REV-04 | unit | `pytest tests/test_clinical_models.py::TestPatientSummary -x` | Wave 0 | ⬜ pending |
| 04-02-07 | 02 | 1 | REV-04 | unit | `pytest tests/test_extractor.py::test_gpu_handoff_generates_summary -x` | Wave 0 | ⬜ pending |
| 04-02-08 | 02 | 1 | REV-04 | unit | `pytest tests/test_prompts.py::test_patient_summary_prompt -x` | Wave 0 | ⬜ pending |
| 04-03-01 | 03 | 2 | REV-04 | unit | `pytest tests/test_review_routes.py -x` | Exists (update) | ⬜ pending |
| 04-03-02 | 03 | 2 | REV-04 | smoke | Manual: open print preview in browser | Manual only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_vocab.py` — stubs for CLI-05 (custom vocab loading, merge logic)
- [ ] `tests/test_prompts.py` — stubs for CLI-06 (template composition) and REV-04 (patient summary prompt)
- [ ] Update `tests/test_speaker.py` — add assistant classification test cases for CLI-07
- [ ] Update `tests/test_speaker_reattribution.py` — add 3-role reattribution tests for CLI-07
- [ ] Update `tests/test_clinical_models.py` — add AppointmentType, PatientSummary model tests
- [ ] Update `tests/test_extractor.py` — add template-aware extraction, patient summary generation tests
- [ ] Update `tests/test_whisper_service.py` — add hotwords parameter acceptance test
- [ ] Update `tests/test_review_routes.py` — add tab rendering and patient summary display tests
- [ ] Update `tests/test_session_store.py` — add appointment_type field persistence tests
- [ ] Update `tests/conftest.py` — add FakeOllamaService variant returning patient summary data

*Existing test infrastructure (249 tests) covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Print CSS hides non-print elements | REV-04 | Browser print preview requires interactive verification | Open patient summary tab, Ctrl+P, verify only summary content appears |
| Whisper transcription quality improved | CLI-05 | Subjective quality assessment on real dental speech | Record a dental conversation, compare v1 vs v2 transcription accuracy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
