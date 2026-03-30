---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Production & Clinical
status: completed
stopped_at: Phase 5 executing — 05-03 checkpoint pending, UI refinements in progress (SOAP restructure, workflow tabs, scrub feature)
last_updated: "2026-03-30T03:51:54.427Z"
last_activity: 2026-03-30 -- Completed 05-02 (auto-pause, next-patient, auto-save, mic disconnect, Whisper OOM retry)
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 18
  completed_plans: 16
  percent: 89
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-28)

**Core value:** Reliably record, transcribe, and produce a usable clinical note from a real dental appointment -- every time, with no data leaving the building.
**Methodology:** Pragmatic TDD -- test file before implementation, integration tests mandatory, human verification gates are blocking
**Current focus:** v2.0 Phase 5 -- Workflow and Recovery (batch multi-patient, auto-pause, error recovery, health monitoring)
**Tests:** 436 passing (up from 411)

## Current Position

Phase: 5 of 6 (Workflow and Recovery) -- IN PROGRESS
Plan: 2 of 3 complete
Status: Plan 05-02 complete, ready for 05-03
Last activity: 2026-03-30 -- Completed 05-02 (auto-pause, next-patient, auto-save, mic disconnect, Whisper OOM retry)

Progress: [█████████████████░░░] 89%

## What Works Now

- **v1.0 complete and human-verified** -- full pipeline: record -> transcribe -> extract SOAP -> review -> copy -> finalize
- **436 tests passing** across all modules
- **Server runs on Windows Python** with Yeti Classic mic, NVIDIA GPU (faster-whisper int8/CUDA)
- **Ollama + Qwen3 8B** for clinical extraction (SOAP + CDT codes + speaker re-attribution)
- **Review UI**: 50/50 split, full editing, dictation, clipboard copy, session list, finalize + cleanup
- **GPU handoff**: Whisper unload -> LLM extract -> LLM unload -> Whisper reload (8GB VRAM budget)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 12
- Average duration: 6.4min
- Total execution time: 1.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Streaming Capture | 3 | 9min | 3min |
| 1.1 Test Hardening | 3 | 14min | 4.7min |
| 2. Clinical Extraction | 3 | 33min | 11min |
| 3. Review and Export | 3 | 29min | 9.7min |
| 4. Clinical Intelligence | 3 | 28min | 9.3min |
| 5. Workflow & Recovery | 2 | 23min | 11.5min |

## Accumulated Context

### Decisions

Recent decisions affecting current work:
- [04-01]: Doctor-wins-ties in 3-way speaker classification when assistant=doctor score
- [04-01]: Custom vocab loaded at WhisperService init, not per-transcribe call
- [04-01]: vocab.py owns all vocabulary constants; whisper_service.py imports from it
- [v2.0]: 3-way speaker ID via text classifier + LLM re-attribution (pyannote ruled out -- 6-9GB VRAM)
- [v2.0]: Auto-pause is safety net; manual "Next Patient" is primary batch mechanism
- [v2.0]: Patient summary piggybacks on SOAP extraction (second LLM call in same GPU handoff window)
- [v2.0]: Template composition -- base SOAP prompt + template-specific overlays
- [v2.0]: Task Scheduler for auto-start, not Windows service (Session 0 blocks audio/GPU)
- [v2.0]: Embedded Python + Inno Setup for installer (not PyInstaller -- CUDA DLL issues)
- [v2.0]: Split architecture for multi-machine -- workstations record+transcribe, GPU machine runs Ollama + hosts review UI
- [04-02]: Template overlays are short (3-5 lines) appended to base prompt, not full rewrites
- [04-02]: Auto-detection uses plain-text generate() for lightweight classification, falls back to "general"
- [04-02]: Patient summary uses transcript as input (not SOAP) to avoid jargon bleed
- [04-02]: Summary failure is graceful -- logs warning, extraction still succeeds
- [04-03]: Template selection moved from pre-recording dropdown to review page -- auto-detect is primary, manual override on review
- [04-03]: Tab state preserved via data-active-tab attribute restored in htmx:afterSwap handler
- [04-03]: Print summary is standalone HTML page (not partial) with own @media print CSS
- [05-01]: Disk health check falls back to parent dir if storage_dir not yet created
- [05-01]: Custom retry predicate for selective CUDA OOM RuntimeError retry
- [05-01]: list_sessions() default excludes INCOMPLETE for backward compat
- [05-01]: _incomplete_{id}.json naming separates crash recovery from completed sessions
- [05-02]: Rolling buffer cleared at START of auto-pause entry to prevent replay of already-transcribed audio
- [05-02]: 3 consecutive speech blocks (300ms) required to confirm resume from auto-pause
- [05-02]: next_patient() does NOT trigger extraction -- deferred to review for fast transitions
- [05-02]: Mic disconnect via block arrival timing, not PortAudioError (USB may not raise immediately)
- [05-02]: Whisper OOM saves raw .npy audio to recovery_audio/ instead of crashing
- [05-02]: Auto-save try/except prevents store failure from crashing processing loop

### Pending Todos

None yet.

### Blockers/Concerns

- Whisper initial_prompt expanded to cover all 4 categories within ~224 token budget (resolved by 04-01)
- CUDA versions on operatory PCs not yet surveyed (needed before Phase 6)
- Ollama bundling vs prerequisite decision deferred to Phase 6 planning

## Session Continuity

Last session: 2026-03-30T03:51:54.405Z
Stopped at: Phase 5 executing — 05-03 checkpoint pending, UI refinements in progress (SOAP restructure, workflow tabs, scrub feature)
Resume action: Execute 05-03-PLAN.md (health dashboard and workflow routes)
