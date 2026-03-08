# Dental Notes — Project State

> Last updated: 2026-03-06
> Status: **GSD initialized — ready to plan Phase 1**

---

## Current Project: Ambient Clinical Intelligence (v2)

Local-first ambient clinical note-taking tool for dental practices. Records appointment conversations via inconspicuous microphone, transcribes in streaming chunks via faster-whisper on local NVIDIA GPU, uses a local LLM (Ollama) to filter chitchat and structure clinical content into SOAP notes with CDT codes. All processing on-premise — no patient data leaves the office network.

**Repository:** `https://github.com/Deeps-Plato/dental-notes.git`
**Local path:** `~/claude/dental-notes/`

### GSD Planning

| Artifact | Location |
|----------|----------|
| Project | `.planning/PROJECT.md` |
| Config | `.planning/config.json` |
| Research | `.planning/research/` |
| Requirements | `.planning/REQUIREMENTS.md` |
| Roadmap | `.planning/ROADMAP.md` |
| GSD State | `.planning/STATE.md` |

### Methodology

**Pragmatic TDD** — test file before implementation file, integration tests mandatory per phase, human verification checkpoints are blocking gates. Adopted after v1 delivered 128 passing tests and zero working product.

### Roadmap (4 phases)

| Phase | Name | Requirements | Status |
|-------|------|-------------|--------|
| 1 | Streaming Capture & Transcription | AUD-01, TRX-01, TRX-02, PRV-01 | Code complete, awaiting verification |
| 1.1 | Phase 1 Test Hardening | AUD-01, TRX-01, TRX-02, PRV-01 | Not started |
| 2 | Clinical Extraction | CLI-01, CLI-02, CLI-03 | Not started |
| 3 | Review & Export | REV-01, REV-02, REV-03, REV-04, AUD-02 | Not started |

### Key Architecture Decisions

- **Streaming transcription**: Audio chunks transcribed and discarded immediately — no full WAV stored
- **Local-only processing**: faster-whisper + Ollama (Qwen3 8B) — no cloud APIs
- **Minimum hardware**: GTX 1050 (4GB VRAM) — small Whisper model required
- **Sequential GPU loading**: Whisper and LLM cannot coexist in VRAM
- **Web UI**: FastAPI + HTMX at localhost — no Electron, no Flutter
- **Pipeline-first**: Prove record → transcribe → structure before building UI

### Next Step

`/gsd:plan-phase 1.1` — plan the test hardening phase, then execute it before moving to Phase 2

---

## Legacy Codebase (v1 — archived reference)

The existing Flutter + FastAPI code (phases 0-7, 128 tests) was built in a previous milestone but did not produce a working product. It remains in the repo as reference only. The v2 approach rebuilds from scratch with a local-first, streaming architecture.

### What Exists (reference only)

| Component | Status |
|-----------|--------|
| Flutter app (iOS/Android/Windows/macOS) | 41 files, ~4,600 LOC, 115 tests |
| FastAPI backend (Whisper + Claude) | 17 files, ~800 LOC, 13 tests |
| SQLCipher local DB (7 tables, schema v2) | Built but unused |

### Dev Commands (legacy)

```bash
# Flutter (legacy — not part of v2)
cd ~/claude/dental-notes/app
~/flutter/bin/flutter test

# Backend (legacy — not part of v2)
cd ~/claude/dental-notes/backend
source .venv/bin/activate
pytest tests/
```
