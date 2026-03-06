# Requirements: Dental Notes — Ambient Clinical Intelligence

**Defined:** 2026-03-06
**Core Value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment — every time, with no data leaving the building.

## v1 Requirements

### Audio

- [ ] **AUD-01**: User can start and stop ambient audio recording of a dental appointment
- [ ] **AUD-02**: Audio and transcript are automatically deleted after the note is finalized

### Transcription

- [ ] **TRX-01**: Audio is transcribed locally using faster-whisper on NVIDIA GPU
- [ ] **TRX-02**: Transcription uses a dental terminology vocabulary prompt for accuracy

### Clinical Intelligence

- [ ] **CLI-01**: Local LLM filters clinical content from social conversation/chitchat
- [ ] **CLI-02**: Filtered content is structured into a dental SOAP note (Subjective, Objective, Assessment, Plan)
- [ ] **CLI-03**: CDT procedure codes are suggested from the Assessment/Plan sections

### Review & Export

- [ ] **REV-01**: User can view full transcript side-by-side with the structured SOAP note draft
- [ ] **REV-02**: User can edit the AI-generated SOAP note before finalizing
- [ ] **REV-03**: User can copy the finalized note to clipboard in one click (Dentrix-ready format)
- [ ] **REV-04**: A plain-language patient summary is generated alongside the clinical note

### Privacy

- [ ] **PRV-01**: All processing runs locally — no patient data transmitted over the internet

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
| Real-time streaming transcript during procedure | Distracts dentist; worse accuracy; massive complexity for no user value |
| Dentrix API integration | Proprietary, poorly documented, requires vendor partnership; copy-paste suffices |
| Patient identity/records database | Creates PHI liability; Dentrix is the system of record |
| Always-on continuous recording | Legal nightmare in two-party consent state; generates unusable volumes of audio |
| Autonomous note finalization without review | 19.5% transcript error transmission rate; malpractice risk |
| Voice-activated perio charting | Requires extremely high numeric accuracy; separate validation cycle; v2+ |
| Cloud-based processing | Violates privacy-first principle; no patient data leaves the building |
| Mobile/tablet recording app | Previous Flutter mobile attempt failed; desktop-first with proven hardware |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUD-01 | — | Pending |
| AUD-02 | — | Pending |
| TRX-01 | — | Pending |
| TRX-02 | — | Pending |
| CLI-01 | — | Pending |
| CLI-02 | — | Pending |
| CLI-03 | — | Pending |
| REV-01 | — | Pending |
| REV-02 | — | Pending |
| REV-03 | — | Pending |
| REV-04 | — | Pending |
| PRV-01 | — | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 0
- Unmapped: 12

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 after initial definition*
