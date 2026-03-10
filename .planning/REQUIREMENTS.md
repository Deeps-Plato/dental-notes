# Requirements: Dental Notes — Ambient Clinical Intelligence

**Defined:** 2026-03-06
**Core Value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment — every time, with no data leaving the building.

## v1 Requirements

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
- [ ] **REV-04**: A plain-language patient summary is generated alongside the clinical note

### Privacy

- [x] **PRV-01**: All processing runs locally — no patient data transmitted over the internet

## v2 Requirements

### Recording Workflow

- **REC-01**: Software consent gate prevents recording before explicit acknowledgment
- **REC-02**: Session management tracks multiple appointments per day with metadata

### Clinical Enhancements

- **ENH-01**: Appointment-type templates (exam, restorative, hygiene, endo, extraction)
- **ENH-02**: Speaker diarization distinguishes dentist from patient from assistant
- **ENH-03**: Expanded dental terminology Whisper prompt for improved accuracy

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live transcript display during procedure | Distracts dentist; no clinical value during active work; transcript accumulates silently in the background |
| Dentrix API integration | Proprietary, poorly documented, requires vendor partnership; copy-paste suffices |
| Patient identity/records database | Creates PHI liability; Dentrix is the system of record |
| Always-on continuous recording | Legal nightmare in two-party consent state; generates unusable volumes of audio |
| Autonomous note finalization without review | 19.5% transcript error transmission rate; malpractice risk |
| Voice-activated perio charting | Requires extremely high numeric accuracy; separate validation cycle; v2+ |
| Cloud-based processing | Violates privacy-first principle; no patient data leaves the building |
| Mobile/tablet recording app | Previous Flutter mobile attempt failed; desktop-first with proven hardware |
| Storing full appointment audio | Streaming architecture transcribes chunks and discards audio immediately; no full WAV needed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUD-01 | Phase 1 | Complete |
| AUD-02 | Phase 3 | Complete |
| TRX-01 | Phase 1 | Complete |
| TRX-02 | Phase 1 | Complete |
| CLI-01 | Phase 2 | Complete |
| CLI-02 | Phase 2 | Complete |
| CLI-03 | Phase 2 | Complete |
| CLI-04 | Phase 2 | Complete |
| REV-01 | Phase 3 | Complete |
| REV-02 | Phase 3 | Complete |
| REV-03 | Phase 3 | Complete |
| REV-04 | Phase 3 | Pending |
| PRV-01 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 after roadmap revision (streaming architecture)*
