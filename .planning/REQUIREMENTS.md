# Requirements: Dental Notes — Ambient Clinical Intelligence

**Defined:** 2026-03-06 (v1), updated 2026-03-29 (v2.0)
**Core Value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment — every time, with no data leaving the building.

## v1 Requirements (Complete)

### Audio

- [x] **AUD-01**: User can start and stop a streaming capture session that records audio in small chunks, transcribes each chunk immediately, and discards the audio — no full-length recording is ever stored
- [x] **AUD-02**: Transcript file is automatically deleted after the note is finalized

### Transcription

- [x] **TRX-01**: Audio chunks are transcribed locally using faster-whisper on NVIDIA GPU, with a model small enough to run on GTX 1050 (4GB VRAM)
- [x] **TRX-02**: Transcription uses a dental terminology vocabulary prompt for accuracy

### Clinical Intelligence

- [x] **CLI-01**: Local LLM filters clinical content from social conversation/chitchat
- [x] **CLI-02**: Filtered content is structured into a dental SOAP note (Subjective, Objective, Assessment, Plan)
- [x] **CLI-03**: CDT procedure codes are suggested from the Assessment/Plan sections
- [x] **CLI-04**: LLM re-attributes speaker labels (Doctor/Patient) using conversational context — who leads, instructs, and directs vs who responds and reports symptoms

### Review & Export

- [x] **REV-01**: User can view full transcript side-by-side with the structured SOAP note draft
- [x] **REV-02**: User can edit the AI-generated SOAP note before finalizing
- [x] **REV-03**: User can copy the finalized note to clipboard in one click (Dentrix-ready format)

### Privacy

- [x] **PRV-01**: All processing runs locally — no patient data transmitted over the internet

## v2.0 Requirements

### Clinical Intelligence

- [x] **CLI-05**: Whisper vocabulary expanded with procedures, materials, surfaces, pathology, anatomy, findings, and diagnoses using initial_prompt + hotwords parameter
- [x] **CLI-06**: 5 appointment-type templates (comprehensive exam, restorative, hygiene/recall, endodontic, oral surgery) with template-specific extraction prompts and note structures
- [x] **CLI-07**: 3-way speaker classification (Doctor/Patient/Assistant) via extended text-based keyword classifier + LLM re-attribution with zero additional VRAM
- [x] **REV-04**: Plain-language patient summary generated at 6th-grade reading level alongside clinical SOAP note

### Workflow

- [ ] **WRK-01**: Batch session management — multi-patient day mode with "Next Patient" flow and end-of-day review queue
- [ ] **WRK-02**: Auto-pause on extended silence (configurable threshold) with auto-resume when new speech is detected — system always listens even when paused
- [x] **WRK-03**: Error recovery — retry logic for Ollama/GPU/mic failures with graceful degradation; session data never lost on crash
- [x] **WRK-04**: Health check endpoint (/api/health) reporting GPU status, Ollama reachability, mic availability

### Deployment

- [ ] **DPL-01**: Windows installer (embedded Python + Inno Setup) that detects CUDA version, installs dependencies, and pre-downloads Whisper model
- [ ] **DPL-02**: Auto-start on boot via Windows Task Scheduler "At logon" trigger
- [ ] **DPL-03**: Split-architecture multi-machine config — workstations record + transcribe locally, separate GPU machine runs Ollama extraction and hosts review/finalization UI
- [ ] **DPL-04**: Deployment documentation for replicating setup on new operatory PCs

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live transcript display during procedure | Distracts dentist; no clinical value during active work; transcript accumulates silently in the background |
| Dentrix API integration | Proprietary, poorly documented, requires vendor partnership; copy-paste suffices |
| Patient identity/records database | Creates PHI liability; Dentrix is the system of record |
| Always-on continuous recording | Legal nightmare in two-party consent state; generates unusable volumes of audio |
| Autonomous note finalization without review | 19.5% transcript error transmission rate; malpractice risk |
| Voice-activated perio charting | Requires extremely high numeric accuracy; separate validation cycle; v3+ |
| Cloud-based processing | Violates privacy-first principle; no patient data leaves the building |
| Mobile/tablet recording app | Previous Flutter mobile attempt failed; desktop-first with proven hardware |
| Storing full appointment audio | Streaming architecture transcribes chunks and discards audio immediately; no full WAV needed |
| Fine-tuning Whisper on dental data | Research project, not product feature; initial_prompt/hotwords approach is sufficient |
| Real-time SOAP streaming during recording | GPU handoff would create transcription gaps; post-stop extraction is fast (10-30s) |
| pyannote speaker diarization | 6-9GB VRAM exceeds target hardware; text-based + LLM re-attribution is sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUD-01 | v1 Phase 1 | Complete |
| AUD-02 | v1 Phase 3 | Complete |
| TRX-01 | v1 Phase 1 | Complete |
| TRX-02 | v1 Phase 1 | Complete |
| CLI-01 | v1 Phase 2 | Complete |
| CLI-02 | v1 Phase 2 | Complete |
| CLI-03 | v1 Phase 2 | Complete |
| CLI-04 | v1 Phase 2 | Complete |
| REV-01 | v1 Phase 3 | Complete |
| REV-02 | v1 Phase 3 | Complete |
| REV-03 | v1 Phase 3 | Complete |
| PRV-01 | v1 Phase 1 | Complete |
| CLI-05 | Phase 4 | Complete |
| CLI-06 | Phase 4 | Complete |
| CLI-07 | Phase 4 | Complete |
| REV-04 | Phase 4 | Complete |
| WRK-01 | Phase 5 | Pending |
| WRK-02 | Phase 5 | Pending |
| WRK-03 | Phase 5 | Complete |
| WRK-04 | Phase 5 | Complete |
| DPL-01 | Phase 6 | Pending |
| DPL-02 | Phase 6 | Pending |
| DPL-03 | Phase 6 | Pending |
| DPL-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 12 total (all complete)
- v2.0 requirements: 12 total
- Mapped to phases: 12/12
- Unmapped: 0

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-29 — v2.0 requirements mapped to Phases 4-6*
