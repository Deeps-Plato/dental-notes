# Roadmap: Dental Notes — Ambient Clinical Intelligence

## Overview

This roadmap delivers a local-first ambient clinical note-taking tool in 3 phases, following a streaming pipeline architecture: capture audio in small chunks, transcribe each chunk immediately via faster-whisper, discard the audio, accumulate the transcript, then extract clinical content and build the review workflow. The key architectural shift from the prior plan is that audio capture and transcription are inseparable — audio chunks are ephemeral, transcribed on arrival, and never stored as a full recording. This minimizes disk usage and proves the core pipeline in a single phase. The tool must run on GPUs as small as GTX 1050 (4GB VRAM), so Whisper model selection is constrained to smaller models.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Streaming Capture and Transcription** - Stream audio chunks from mic, transcribe each chunk locally via faster-whisper, discard audio, accumulate transcript
- [x] **Phase 1.1: Phase 1 Test Hardening** *(INSERTED)* - Fill test coverage gaps, add pipeline integration test, complete human verification
- [ ] **Phase 2: Clinical Extraction** - Filter clinical content from accumulated transcript and generate structured SOAP notes via local LLM
- [ ] **Phase 3: Review and Export** - Side-by-side review UI with editing, clipboard export, and ephemeral cleanup

## Phase Details

### Phase 1: Streaming Capture and Transcription
**Goal**: User can start an appointment session that continuously captures audio in small chunks, transcribes each chunk locally via faster-whisper, discards the audio, and accumulates a growing text transcript — all on the local GPU with minimal VRAM usage
**Depends on**: Nothing (first phase)
**Requirements**: AUD-01, TRX-01, TRX-02, PRV-01
**Success Criteria** (what must be TRUE):
  1. User can select a microphone, start a session, and see transcript text accumulating progressively as the appointment proceeds
  2. Each audio chunk is transcribed within seconds and the audio data is discarded — no full-length WAV is ever stored on disk
  3. Dental terminology (tooth numbers, procedure names, materials) appears correctly in the transcript due to vocabulary prompting
  4. The tool runs on a GTX 1050 with 4GB VRAM without running out of GPU memory (small Whisper model selected accordingly)
  5. No network requests are made during the session — all capture and transcription stays on the local machine
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Project setup + core audio pipeline (capture, VAD, chunker, stitcher, transcript writer)
- [x] 01-02-PLAN.md — Whisper transcription service + session manager state machine
- [x] 01-03-PLAN.md — FastAPI web UI with SSE, HTMX templates, keyboard shortcuts, end-to-end verification

### Phase 1.1: Phase 1 Test Hardening *(INSERTED)*
**Goal**: Fill test coverage gaps in Phase 1, add a pipeline integration test that proves components actually connect, and complete the human verification checkpoint — ensuring Phase 1 delivers working software, not just passing tests
**Depends on**: Phase 1
**Requirements**: AUD-01, TRX-01, TRX-02, PRV-01 (hardening existing requirement coverage)
**Success Criteria** (what must be TRUE):
  1. Every production module has a dedicated test file with meaningful behavioral tests (not just import checks)
  2. A pipeline integration test exercises: audio input → VAD → chunker → whisper service → stitcher → transcript writer (with realistic fakes, not canned mocks)
  3. The integration test proves components connect — data flows through the full chain and produces a transcript
  4. Human verification checkpoint from Plan 01-03 is completed (user confirms the app works on real hardware)
  5. All tests pass and the test suite serves as a reliable signal (if tests pass, the thing works)
**Plans:** 3/3 plans complete

Plans:
- [x] 01.1-01-PLAN.md — Consolidate shared test fakes in conftest + unit tests for AudioCapture and HotkeyListener
- [x] 01.1-02-PLAN.md — App factory tests + pipeline integration test proving end-to-end data flow
- [x] 01.1-03-PLAN.md — Full test suite verification + human verification checkpoint (blocking gate)

### Phase 2: Clinical Extraction
**Goal**: A local LLM filters clinical content from the accumulated transcript and structures it into a SOAP note with CDT procedure code suggestions
**Depends on**: Phase 1
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. Social conversation and chitchat are filtered out, leaving only clinically relevant content
  2. Filtered content is structured into a dental SOAP note with Subjective, Objective, Assessment, and Plan sections
  3. CDT procedure codes are suggested based on the Assessment and Plan sections
  4. All LLM processing runs locally via Ollama — no patient data leaves the machine
  5. Speaker labels (Doctor/Patient) are re-attributed by the LLM using conversational context, correcting keyword-based misclassifications from Phase 1
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Review and Export
**Goal**: User can review transcript and SOAP note side-by-side, edit the draft, copy the finalized note for Dentrix, and have ephemeral data automatically cleaned up
**Depends on**: Phase 2
**Requirements**: REV-01, REV-02, REV-03, REV-04, AUD-02
**Success Criteria** (what must be TRUE):
  1. User sees the full accumulated transcript alongside the AI-generated SOAP note draft in a side-by-side view
  2. User can edit any section of the SOAP note draft before finalizing
  3. User can copy the finalized note to clipboard in one click, formatted for Dentrix paste
  4. A plain-language patient summary is generated alongside the clinical note
  5. After finalization, the transcript file is automatically deleted from disk (audio was already discarded during capture)
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 1.1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Streaming Capture and Transcription | 3/3 | Complete | 2026-03-07 |
| 1.1. Phase 1 Test Hardening *(INSERTED)* | 3/3 | Complete   | 2026-03-09 |
| 2. Clinical Extraction | 0/2 | Not started | - |
| 3. Review and Export | 0/3 | Not started | - |
