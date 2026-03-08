# Dental Notes — Ambient Clinical Intelligence

## What This Is

A privacy-first ambient clinical note-taking tool for dental practices. Records appointment conversations using an inconspicuous microphone, transcribes locally via Whisper, and uses a local LLM to filter out social conversation and extract clinical content into structured SOAP notes with CDT procedure codes. The dentist reviews a draft alongside the full transcript, edits as needed, and copy-pastes the final note into Dentrix. All processing stays on-premise — no patient data leaves the office network.

## Core Value

The tool must reliably record, transcribe, and produce a usable clinical note from a real dental appointment — every time, with no data leaving the building.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Ambient audio recording of dental appointments via inconspicuous microphone
- [ ] Local speech-to-text transcription (faster-whisper on NVIDIA GPU)
- [ ] AI filtering of clinical content from social conversation/chitchat
- [ ] Structured SOAP note generation from filtered clinical content
- [ ] CDT procedure code extraction/suggestion from appointment context
- [ ] Full transcript view (temporarily available for review)
- [ ] Side-by-side view: full transcript vs. structured SOAP note draft
- [ ] Editable draft mode — dentist can review and tweak before finalizing
- [ ] One-click copy of finalized note for paste into Dentrix
- [ ] Automatic cleanup — recording and transcript discarded after note is finalized
- [ ] Local-only processing — no patient data transmitted over the internet
- [ ] State-by-state recording consent reference (Florida priority)

### Out of Scope

- Cloud-based transcription or AI APIs — violates privacy-first principle
- Native iOS/Android mobile app — evaluate form factor during research first
- Dentrix API integration — copy-paste workflow is sufficient for v1
- Patient records database — this is a note-generation tool, not an EHR
- Multi-provider support — single dentist (Deep) for v1
- Pay-as-you-go pricing model — all processing must be free/local

## Context

### Prior Work

An existing Flutter + FastAPI codebase exists in this repo (phases 0-7, 128 tests) but **did not produce a working product** — recording didn't transcribe, files weren't saved. The previous architecture (cloud Whisper + Claude API + Flutter cross-platform) was overengineered and unreliable. This new initiative starts fresh with a local-first, actually-executable approach.

### Competitive Landscape

Freed AI and Overjet AI offer similar ambient clinical recording + note generation for medical/dental. Deep has seen demos but not used them. Key differentiator: those are cloud-based SaaS; this is fully local/private.

### Office Environment

- All machines: Windows 10/11 with dedicated NVIDIA GPUs (GTX 1050 minimum, most GTX 1070 Ti or better)
- CUDA available on all machines
- Dentrix runs on the same Windows desktops
- Appointments: mix of quick exams (10-15 min, quiet, 2 people) and longer procedures (20-30 min, 3+ people, more noise)
- Volume: 5-10 patients/day initially
- Whisper-PTT already proven effective on Deep's home machine

### HIPAA & Privacy

- Patient audio must never leave the local machine
- Transcripts and recordings must be ephemeral — discarded after note is finalized
- Florida is a two-party consent state — patient consent required for recording
- Deep wants a reference document covering all US states' recording consent laws

## Constraints

- **Hardware**: Windows 10/11 + NVIDIA GPU (GTX 1050+, most 1070 Ti+) — must run on existing office machines
- **Privacy**: Zero cloud dependency for patient data — all transcription and AI processing local
- **Cost**: No per-use API fees — free/local processing only
- **Reliability**: Must actually work end-to-end — no more "code that doesn't produce a product"
- **Professionalism**: Microphone must be inconspicuous — patients shouldn't feel surveilled
- **Timeline**: ASAP — needs to be usable quickly, not a months-long project

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local-only processing | HIPAA compliance + professional obligation to patient privacy | -- Pending |
| Whisper for transcription | Proven effective (whisper-ptt), runs on available NVIDIA hardware, free | -- Pending |
| Local LLM for note structuring | No API costs, no data leaving premises; quality TBD during research | -- Pending |
| Copy-paste to Dentrix | Simplest reliable integration; API integration out of scope for v1 | -- Pending |
| Evaluate mic hardware | Need inconspicuous option that works in clinical setting; research phase | -- Pending |
| Evaluate form factor | Desktop app vs phone/tablet vs web UI — research phase will determine | -- Pending |
| Model profile: Quality (Opus) | User requested Opus for deep thinking during planning | -- Pending |
| Pragmatic TDD (red-green-refactor) | v1 had 128 tests and didn't produce a working product. Tests must verify behavior that matters to the user, not just internal correctness with mocks. Test file first, then implementation. | Adopted |

## Development Methodology: Pragmatic TDD

### The Problem This Solves

v1 delivered 128 passing tests and zero working product. The tests verified mocked internals — not real behavior. Passing tests gave false confidence while the actual pipeline (record → transcribe → note) never worked end-to-end.

### Rules

1. **Test file before implementation file.** For each task, write the test file first. Define expected behavior as assertions. Run the tests — they must fail (red). Then write the implementation to make them pass (green). Refactor if needed.

2. **Tests must verify what the user cares about.** "Session manager returns transcript" matters. "Mock returns canned string" does not. Every test should answer: *if this test passes, does the user get something that works?*

3. **Integration tests are mandatory per phase.** Each phase must include at least one integration test that exercises the full pipeline for that phase with realistic fakes (not mocks that return canned data). The integration test should prove the components actually connect.

4. **Hardware-dependent code gets boundary tests.** Audio capture, GPU inference, and OS-level features can't run in CI. Test the boundaries: verify the interface contract, test with fake implementations that behave like the real thing, and require human verification for the actual hardware path.

5. **Human verification checkpoints are blocking gates.** No phase is complete until the human checkpoint passes. "Tests pass" is necessary but not sufficient — the user must confirm the thing actually works.

6. **No mocking away the thing you're testing.** If you're testing that transcription works, the test must actually run text through the pipeline — not mock the transcription service to return a canned string.

### What Gets Tested vs What Doesn't

| Test | Don't Test |
|------|------------|
| Business logic and data transformations | HTML templates and CSS |
| Pipeline integration (components connected) | Third-party library internals |
| Error handling and edge cases | Trivial getters/setters |
| State machines and transitions | Configuration loading (unless complex) |
| API route behavior with realistic fakes | Exact log messages |

---
*Last updated: 2026-03-07 — added TDD methodology*
