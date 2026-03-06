# Roadmap: Dental Notes — Ambient Clinical Intelligence

## Overview

This roadmap delivers a local-first ambient clinical note-taking tool in 4 phases, following the pipeline that the previous attempt never proved: capture audio, transcribe it, extract clinical content, then build the review workflow. Each phase produces a concrete artifact (WAV file, transcript, SOAP note, usable UI) that can be manually verified before proceeding. No infrastructure or UI work happens until the core pipeline is proven.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Audio Capture** - Record dental appointments locally with mic selection and privacy enforcement
- [ ] **Phase 2: Transcription Pipeline** - Transcribe recorded audio locally using faster-whisper with dental vocabulary
- [ ] **Phase 3: Clinical Extraction** - Filter clinical content and generate structured SOAP notes via local LLM
- [ ] **Phase 4: Review and Export** - Side-by-side review UI with editing, clipboard export, and ephemeral cleanup

## Phase Details

### Phase 1: Audio Capture
**Goal**: User can record a dental appointment to a local WAV file using a selected microphone, with all processing staying on the local machine
**Depends on**: Nothing (first phase)
**Requirements**: AUD-01, PRV-01
**Success Criteria** (what must be TRUE):
  1. User can select a microphone from available audio devices and start/stop recording an appointment
  2. Recording is saved as a playable WAV file on the local machine with speech clearly captured
  3. No network requests are made during recording — all audio stays on the local filesystem
  4. User can play back the recorded audio to verify speech quality against dental equipment noise
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Transcription Pipeline
**Goal**: User can transcribe a recorded appointment locally using faster-whisper with dental-specific vocabulary, producing an accurate text transcript
**Depends on**: Phase 1
**Requirements**: TRX-01, TRX-02
**Success Criteria** (what must be TRUE):
  1. User can trigger transcription of a recorded WAV file and receive a text transcript within minutes
  2. Transcription runs entirely on the local NVIDIA GPU via faster-whisper — no cloud API calls
  3. Dental terminology (tooth numbers, procedure names, materials) is transcribed accurately due to vocabulary prompting
  4. Silent segments during procedures do not produce hallucinated text (VAD preprocessing filters them)
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Clinical Extraction
**Goal**: A local LLM filters clinical content from a dental transcript and structures it into a SOAP note with CDT procedure code suggestions
**Depends on**: Phase 2
**Requirements**: CLI-01, CLI-02, CLI-03
**Success Criteria** (what must be TRUE):
  1. Social conversation and chitchat are filtered out, leaving only clinically relevant content
  2. Filtered content is structured into a dental SOAP note with Subjective, Objective, Assessment, and Plan sections
  3. CDT procedure codes are suggested based on the Assessment and Plan sections
  4. All LLM processing runs locally via Ollama — no patient data leaves the machine
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Review and Export
**Goal**: User can review transcript and SOAP note side-by-side, edit the draft, copy the finalized note for Dentrix, and have recordings automatically cleaned up
**Depends on**: Phase 3
**Requirements**: REV-01, REV-02, REV-03, REV-04, AUD-02
**Success Criteria** (what must be TRUE):
  1. User sees the full transcript alongside the AI-generated SOAP note draft in a side-by-side view
  2. User can edit any section of the SOAP note draft before finalizing
  3. User can copy the finalized note to clipboard in one click, formatted for Dentrix paste
  4. A plain-language patient summary is generated alongside the clinical note
  5. After finalization, the recording and transcript are automatically deleted from disk
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Audio Capture | 0/2 | Not started | - |
| 2. Transcription Pipeline | 0/2 | Not started | - |
| 3. Clinical Extraction | 0/2 | Not started | - |
| 4. Review and Export | 0/3 | Not started | - |
