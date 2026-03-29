# Roadmap: Dental Notes — Ambient Clinical Intelligence

## Milestones

- [x] **v1.0 MVP** - Phases 1-3 + 1.1 (shipped 2026-03-28)
- [ ] **v2.0 Production & Clinical** - Phases 4-6 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 MVP (Phases 1-3 + 1.1) — SHIPPED 2026-03-28</summary>

- [x] **Phase 1: Streaming Capture and Transcription** - Stream audio chunks from mic, transcribe each chunk locally via faster-whisper, discard audio, accumulate transcript
- [x] **Phase 1.1: Phase 1 Test Hardening** *(INSERTED)* - Fill test coverage gaps, add pipeline integration test, complete human verification
- [x] **Phase 2: Clinical Extraction** - Filter clinical content from accumulated transcript and generate structured SOAP notes via local LLM
- [x] **Phase 3: Review and Export** - Side-by-side review UI with editing, clipboard export, and ephemeral cleanup

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
**Plans:** 3/3 complete

Plans:
- [x] 01-01-PLAN.md — Project setup + core audio pipeline (capture, VAD, chunker, stitcher, transcript writer)
- [x] 01-02-PLAN.md — Whisper transcription service + session manager state machine
- [x] 01-03-PLAN.md — FastAPI web UI with SSE, HTMX templates, keyboard shortcuts, end-to-end verification

### Phase 1.1: Phase 1 Test Hardening *(INSERTED)*
**Goal**: Fill test coverage gaps in Phase 1, add a pipeline integration test that proves components actually connect, and complete the human verification checkpoint
**Depends on**: Phase 1
**Requirements**: AUD-01, TRX-01, TRX-02, PRV-01 (hardening existing requirement coverage)
**Success Criteria** (what must be TRUE):
  1. Every production module has a dedicated test file with meaningful behavioral tests
  2. A pipeline integration test exercises the full chain with realistic fakes
  3. Human verification checkpoint completed
**Plans:** 3/3 complete

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
  5. Speaker labels (Doctor/Patient) are re-attributed by the LLM using conversational context
**Plans:** 3/3 complete

Plans:
- [x] 02-01-PLAN.md — Foundation: Pydantic models, config extension, OllamaService, system prompts with CDT reference
- [x] 02-02-PLAN.md — Clinical pipeline: ClinicalExtractor (SOAP + CDT) and SpeakerReattributor (LLM speaker correction)
- [x] 02-03-PLAN.md — Integration test with real Ollama + human verification checkpoint (blocking gate)

### Phase 3: Review and Export
**Goal**: User can review transcript and SOAP note side-by-side, edit the draft, copy the finalized note for Dentrix, and have ephemeral data automatically cleaned up
**Depends on**: Phase 2
**Requirements**: REV-01, REV-02, REV-03, AUD-02
**Success Criteria** (what must be TRUE):
  1. User sees the full accumulated transcript alongside the AI-generated SOAP note draft in a side-by-side view
  2. User can edit any section of the SOAP note draft before finalizing
  3. User can copy the finalized note to clipboard in one click, formatted for Dentrix paste
  4. After finalization, the transcript file is automatically deleted from disk
**Plans:** 3/3 complete

Plans:
- [x] 03-01-PLAN.md — Session persistence + enriched SoapNote model + clipboard text formatter
- [x] 03-02-PLAN.md — Review UI routes + templates + JavaScript (side-by-side, editing, copy, session list, finalize)
- [x] 03-03-PLAN.md — Dictation on editable fields + human verification checkpoint (blocking gate)

</details>

### v2.0 Production & Clinical (In Progress)

**Milestone Goal:** Transform the working v1 prototype into a production-ready office tool with richer clinical intelligence, batch workflows, and one-click deployment across operatory PCs.

- [ ] **Phase 4: Clinical Intelligence** - Expanded Whisper vocabulary, appointment-type templates, 3-way speaker ID, and patient summary
- [ ] **Phase 5: Workflow and Recovery** - Batch multi-patient day mode, auto-pause/resume, error recovery, and health monitoring
- [ ] **Phase 6: Deployment Infrastructure** - Windows installer, auto-start, split-architecture multi-machine, and deployment docs

## Phase Details

### Phase 4: Clinical Intelligence
**Goal**: The extraction pipeline produces richer, more accurate clinical notes — with procedure-specific templates, 3-way speaker attribution, expanded dental vocabulary, and a plain-language patient summary
**Depends on**: Phase 3 (v1 complete)
**Requirements**: CLI-05, CLI-06, CLI-07, REV-04
**Success Criteria** (what must be TRUE):
  1. Whisper transcribes dental terms across all categories (procedures, materials, surfaces, pathology, anatomy, findings, diagnoses) with noticeably fewer misrecognitions than v1 vocabulary
  2. User can select an appointment type (comprehensive exam, restorative, hygiene/recall, endodontic, oral surgery) and the extracted SOAP note follows that template's structure and emphasis
  3. Transcript chunks are labeled Doctor, Patient, or Assistant — and the LLM re-attribution correctly distinguishes all three roles in a multi-person conversation
  4. A plain-language patient summary at approximately 6th-grade reading level is generated alongside the clinical SOAP note, suitable for patient handout
**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — Expanded Whisper vocabulary + hotwords + custom vocab file + 3-way speaker classification (CLI-05, CLI-07)
- [x] 04-02-PLAN.md — Appointment-type templates + patient summary backend (models, prompts, extraction pipeline, session persistence) (CLI-06, REV-04)
- [ ] 04-03-PLAN.md — Template dropdown UI + patient summary tab/print UI + human verification checkpoint (CLI-06, REV-04)

### Phase 5: Workflow and Recovery
**Goal**: The tool supports a full clinic day — multiple patients recorded in sequence, automatic silence management between patients, graceful recovery from hardware/software failures, and system health visibility
**Depends on**: Phase 4 (templates available for per-session type selection)
**Requirements**: WRK-01, WRK-02, WRK-03, WRK-04
**Success Criteria** (what must be TRUE):
  1. User can record multiple patients in a single day session using a "Next Patient" flow, then review and complete all notes at end of day from a queue
  2. System auto-pauses recording after configurable silence and auto-resumes when new speech is detected — the system always listens even when paused, so no speech is missed at patient transitions
  3. If Ollama crashes, the GPU errors out, or the microphone disconnects mid-session, the system retries automatically and no transcript data is lost
  4. A health check endpoint (/api/health) reports GPU status, Ollama reachability, and microphone availability so the user can verify system readiness before starting a clinic day
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Deployment Infrastructure
**Goal**: Any operatory PC can run the tool via a one-click installer with auto-start, and the office can optionally run a split architecture where workstations handle recording/transcription while a central GPU machine handles LLM extraction and hosts the review UI
**Depends on**: Phase 5 (stable, feature-complete application to package)
**Requirements**: DPL-01, DPL-02, DPL-03, DPL-04
**Success Criteria** (what must be TRUE):
  1. A Windows installer (Inno Setup with embedded Python) installs the tool on a new operatory PC — detecting CUDA version, installing dependencies, and pre-downloading the Whisper model — without requiring any command-line steps
  2. After installation, the server auto-starts on Windows logon via Task Scheduler and is accessible in the browser without manual intervention
  3. In split-architecture mode, a workstation records and transcribes locally while a separate GPU machine runs Ollama extraction and hosts the review/finalization UI — the dentist reviews notes from any machine on the office network
  4. Deployment documentation covers the complete setup process for replicating the system on additional operatory PCs, including both standalone and split-architecture configurations
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 1.1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Streaming Capture and Transcription | v1.0 | 3/3 | Complete | 2026-03-07 |
| 1.1. Phase 1 Test Hardening *(INSERTED)* | v1.0 | 3/3 | Complete | 2026-03-09 |
| 2. Clinical Extraction | v1.0 | 3/3 | Complete | 2026-03-09 |
| 3. Review and Export | v1.0 | 3/3 | Complete | 2026-03-28 |
| 4. Clinical Intelligence | v2.0 | 2/3 | Executing | - |
| 5. Workflow and Recovery | v2.0 | 0/? | Not started | - |
| 6. Deployment Infrastructure | v2.0 | 0/? | Not started | - |
