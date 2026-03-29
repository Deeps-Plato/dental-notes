# Project Research Summary

**Project:** Dental Notes v2.0 — Production & Clinical
**Domain:** Ambient clinical documentation for dental practices
**Researched:** 2026-03-28
**Confidence:** HIGH

## Executive Summary

The v2.0 features split cleanly into three tiers: clinical intelligence enhancements (templates, vocabulary, speaker ID, patient summary) that build directly on existing extraction pipeline; workflow improvements (batch sessions, auto-pause) that extend the SessionManager state machine; and deployment infrastructure (installer, auto-start, error recovery, multi-machine) that wraps the application without modifying internals. The critical constraint remains the 8GB VRAM budget — every feature must work within the sequential GPU handoff pattern (Whisper OR LLM, never both).

The highest-impact finding is that **pyannote-audio is ruled out for 3-way speaker diarization** (6-9GB VRAM, exceeding even the GTX 1070 Ti). The correct approach extends the existing text-based keyword classifier + LLM re-attribution to handle 3 roles (Doctor/Patient/Assistant) with zero additional VRAM. If audio-based embeddings are needed later, resemblyzer (CPU-only, <50MB model) is the fallback.

For Windows deployment, **Windows services are a non-starter** — Session 0 isolation blocks audio device and GPU access. The correct pattern is Windows Task Scheduler with "At logon" trigger (proven by whisper-ptt). For packaging, embedded Python + pip + Inno Setup is more reliable than PyInstaller for CUDA/CTranslate2 bundling. The installer will be 1-2GB (unavoidable with ML dependencies).

## Key Findings

### Recommended Stack

Only 2 new runtime dependencies needed. Most v2 features are pure application logic on the existing stack.

**New dependencies:**
- **tenacity** (>=9.1.0): Retry with backoff for Ollama failures, GPU errors, mic disconnects
- **resemblyzer** (>=0.1.3) + **scikit-learn** (>=1.5.0): CPU-based speaker embeddings for 3-way ID (only if text-based classifier proves insufficient)

**Build tools (not runtime):**
- **Inno Setup 6.x**: Windows installer creation
- **pywin32** (>=310): Task Scheduler registration during install

**No new dependency needed for:** batch workflow, auto-pause, appointment templates, expanded Whisper vocab, patient summary (all pure application logic on existing stack).

### Expected Features

**Must have (table stakes):**
- Batch recording workflow — 5-10 patients/day requires multi-session management
- Error recovery — GPU crash must not lose a patient's transcript
- Expanded Whisper dental vocabulary — current prompt covers ~40% of daily terms
- Auto-pause between patients — prevents recording dead air

**Should have (differentiators):**
- Appointment-type templates — 5 core types (exam, restorative, hygiene, endo, oral surgery)
- 3-way speaker ID (Doctor/Patient/Assistant) — most tools only handle 2
- Plain-language patient summary — no commercial dental tool does this yet
- Windows installer + auto-start — zero command-line deployment

**Anti-features (avoid):**
- Real-time SOAP streaming during recording — GPU handoff would create transcription gaps
- Full pyannote diarization — VRAM budget incompatible
- Always-on continuous recording — Florida two-party consent violation
- Fine-tuning Whisper on dental data — research project, not product feature

### Architecture Approach

Features integrate at three levels: low-touch (vocab expansion, templates, patient summary modify existing files), medium-touch (batch workflow, auto-pause, 3-way speaker add new modules wired into SessionManager), high-touch (installer, auto-start operate outside the app boundary). The existing architecture handles all v2 features with zero VRAM increase.

**Key architectural decisions:**
1. **BatchManager wraps SessionManager** — batch is a layer on top, not a replacement for v1 session lifecycle
2. **Auto-pause = safety net, not primary mechanism** — manual "Next Patient" button is primary; auto-pause fires on 3-5min silence as backup
3. **Patient summary piggybacks on SOAP extraction** — second LLM call within same GPU handoff window
4. **Template composition, not replacement** — base SOAP prompt + template-specific overlays
5. **Task Scheduler, not Windows service** — for auto-start (Session 0 isolation blocks audio/GPU)
6. **Embedded Python + Inno Setup, not PyInstaller** — for reliable CUDA packaging

### Critical Pitfalls

1. **Windows Session 0 isolation** — services cannot access audio or GPU. Use Task Scheduler "At logon" trigger instead of NSSM/pywin32 services.
2. **Breaking v1 pipeline** — v0 died from overengineering. All v2 features must be additive. Run 249+ test suite after every change. Zero regressions.
3. **Speaker diarization VRAM explosion** — pyannote uses 6-9GB VRAM. Extend text-based classifier to 3 roles instead. Zero additional VRAM.
4. **Auto-pause false triggers during procedures** — patient mouth open for 5+ minutes is normal silence during dental work. Use 3-5min threshold, manual "Next Patient" as primary mechanism.
5. **CUDA DLL hell in packaging** — CTranslate2 + CUDA + cuDNN version mismatches cause silent failures. Detect CUDA version at install time, pin exact wheel versions.

## Implications for Roadmap

### Phase 1: Clinical Intelligence
**Rationale:** Highest value, lowest risk. Pure code changes on existing pipeline — no new patterns, no new dependencies. Delivers immediate improvement to note quality.
**Delivers:** Expanded Whisper vocabulary, 5 appointment-type templates, 3-way speaker classification (text-based + LLM), patient summary generation
**Addresses:** All clinical enhancement requirements + REV-04
**Avoids:** Breaking v1 by keeping changes additive to existing extractor/classifier

### Phase 2: Workflow & Recovery
**Rationale:** Enables production use. Batch workflow and error recovery are prerequisites for a real clinic day (5-10 patients). Depends on Phase 1 templates being available for per-session type selection.
**Delivers:** Batch session management, "Next Patient" flow, auto-pause on extended silence, error recovery (tenacity retries, health checks, graceful degradation)
**Addresses:** Batch workflow, auto-pause, error recovery requirements
**Avoids:** Auto-pause pitfall by building manual "Next Patient" first, auto-pause as optional assist

### Phase 3: Deployment Infrastructure
**Rationale:** Wraps a stable, feature-complete application. Packaging before features are stable means constant re-packaging. Building last means the installer captures the final state.
**Delivers:** Windows installer (Inno Setup), auto-start via Task Scheduler, multi-machine config, deployment documentation
**Addresses:** Installer, auto-start, multi-machine requirements
**Avoids:** CUDA DLL packaging issues by using embedded Python + pip instead of PyInstaller

### Phase Ordering Rationale

- Clinical intelligence first because it adds the most user value with the least architectural disruption
- Workflow second because batch mode and error recovery depend on templates being available (appointment type per session)
- Deployment last because packaging a moving target is wasteful — package once when features are stable
- Error recovery woven into Phase 2 rather than standalone — recovery logic is tightly coupled to the components it protects

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Whisper `hotwords` parameter effectiveness for dental terms (needs empirical testing); `initial_prompt` ~224 token limit may already be near capacity
- **Phase 3:** CUDA toolkit version detection across operatory PCs; Ollama bundling vs prerequisite decision; Inno Setup scripting for Task Scheduler registration

Phases with standard patterns (skip research-phase):
- **Phase 2:** Batch workflow and auto-pause are application logic extensions of existing SessionManager; tenacity retry patterns are well-documented

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only 2 new runtime deps; existing stack handles most features |
| Features | HIGH | Dental workflow patterns well-documented; commercial competitor behavior clear |
| Architecture | HIGH | Every existing source file read; integration points specific to file/method level |
| Pitfalls | HIGH | Windows Session 0, VRAM constraints, CUDA packaging all verified via official docs |

**Overall confidence:** HIGH

### Gaps to Address

- **Resemblyzer in dental noise:** CPU-based speaker embeddings untested with dental drill/suction noise. Validate during Phase 1 if text-based classifier proves insufficient.
- **Whisper initial_prompt token budget:** Current prompt uses ~200 of ~224 tokens. Expanding vocabulary requires strategic prioritization or template-specific rotation.
- **CUDA versions on operatory PCs:** Need to survey office machines before Phase 3 to determine CTranslate2 wheel compatibility.
- **Ollama bundling decision:** Ship as prerequisite check or bundle? Affects installer size and complexity.

---
*Research completed: 2026-03-28*
*Ready for roadmap: yes*
