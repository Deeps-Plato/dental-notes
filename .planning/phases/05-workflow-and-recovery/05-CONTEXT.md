# Phase 5: Workflow and Recovery - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Support a full clinic day of recording multiple patients in sequence. "Next Patient" flow saves the current session and starts a new one instantly. Auto-pause detects silence between patients without missing speech on resume. Graceful error recovery handles Ollama/GPU/mic failures with retry logic and no data loss. Health check endpoint and UI status bar show system readiness. All processing stays local.

Phase 4 delivered clinical intelligence (templates, 3-way speaker, patient summary). Phase 5 builds the day-long workflow and resilience on top of the existing pipeline. Phase 6 will handle deployment (installer, auto-start, multi-machine).

</domain>

<decisions>
## Implementation Decisions

### Next Patient flow (WRK-01)
- "Next Patient" button: stops current session, auto-saves, starts a new recording session immediately — no extraction delay between patients
- Extraction happens later during review, not at patient transition (keeps transitions fast)
- No explicit "Start Day" / "End Day" ceremony — sessions are independent, UI groups them by date automatically
- End-of-day review: existing session list page defaults to today's sessions with a "needs review" filter (no new dedicated page)
- Template selection at review time (consistent with Phase 4 decision) — "Next Patient" just starts recording, auto-detect handles appointment type

### Auto-pause intelligence (WRK-02)
- Rolling audio buffer kept during auto-pause — system continuously captures audio even when "paused"
- When VAD detects speech, the rolling buffer (last 5-10 seconds) is included so the first sentence isn't clipped
- Silence threshold: Claude's discretion on default (configurable in settings)
- Visual states: Recording = green pulsing dot + "Recording", Auto-paused = amber dot + "Listening..." (communicates still paying attention), Manual pause = gray "Paused" (existing)
- Auto-pause never triggers "Next Patient" — patient transitions are always a manual button press (avoids accidental session splits from long phone calls or stepping out)

### Error recovery (WRK-03)
- **Extraction failures (Ollama/GPU):** Auto-retry 3 attempts with backoff, non-blocking banner: "Extraction failed, retrying... (2/3)". If all fail, show error with manual retry button. Session data safe regardless.
- **Mic disconnect:** Immediately auto-save transcript captured so far, show prominent alert: "Mic disconnected — transcript saved. Reconnect and resume, or stop session." Dentist decides next step.
- **Whisper transcription failure (GPU OOM mid-chunk):** Buffer the audio and retry after delay. If repeated failures, temporarily save raw audio (exception to no-audio-storage rule) until Whisper recovers. Alert dentist if transcription falling behind.
- **Hard crash (process killed, power outage):** Periodic auto-save of transcript chunks to disk (every N chunks or every 30 seconds). On restart, detect incomplete sessions and offer to resume or finalize. SessionStore's atomic write pattern supports this.

### Health check (WRK-04)
- **API endpoint:** /api/health returning JSON status of all monitored components
- **UI status bar:** Persistent bar in the web UI with green/red indicators — dentist glances at it before starting the day
- **Monitored components:** GPU availability, Ollama reachability, microphone availability, disk space, network connectivity to other machines in the system (relevant for Phase 6 split architecture)
- **Behavior:** Warn only, never block recording (except missing mic — can't record without one). Patient is in the room — better to record with degraded quality than not at all.
- **Refresh rate:** Every 30 seconds via background polling

### Claude's Discretion
- Exact silence threshold default for auto-pause (configurable in settings)
- Rolling buffer size (5 vs 10 seconds)
- Auto-save frequency for crash recovery (every N chunks or time-based)
- Retry backoff timing for extraction failures
- Health status bar visual design and placement
- How network connectivity check works for multi-machine monitoring
- Incomplete session detection and resume/finalize UX on restart

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SessionManager`: State machine (IDLE/RECORDING/PAUSED/STOPPING), background processing thread, manages full capture-to-transcript pipeline — needs new AUTO_PAUSED state and "Next Patient" transition
- `SessionStore`: JSON persistence with atomic writes (temp file + os.replace), create/get/list/update/delete — supports periodic auto-save pattern
- `SavedSession`: Pydantic model with session_id, created_at, status, chunks, extraction_result, appointment_type, patient_summary — may need "incomplete" status for crash recovery
- `VadDetector`: Silero VAD already in pipeline — can drive auto-pause silence detection
- `AudioChunker`: Handles audio segmentation — rolling buffer can be added here
- `OllamaService`: Has health checks already — extend for /api/health endpoint
- `ClinicalExtractor.extract_with_gpu_handoff()`: GPU handoff with finally block — add retry wrapper
- `TranscriptWriter`: Writes transcript to file — adapt for periodic auto-save

### Established Patterns
- FastAPI + HTMX with Jinja2 templates and SSE streaming
- Routes return HTML partials for HTMX swaps (no JSON API for UI)
- Session state machine: IDLE -> RECORDING -> PAUSED -> RECORDING -> IDLE
- GPU memory management via model unload/reload sequences
- Pydantic models for all structured data
- Background daemon thread for audio processing (never blocks asyncio event loop)
- `static/style.css` for all styling, `review.js` for client-side behavior

### Integration Points
- "Next Patient" button: triggers session stop → auto-save → new session start (new route or extends existing stop/start routes)
- Auto-pause: new state in SessionManager state machine, driven by VadDetector silence detection
- Health status bar: new HTMX partial polled every 30 seconds from /api/health
- Error recovery: wraps existing extraction and transcription calls with retry logic
- Crash recovery: periodic writes to sessions/ directory, startup scan for incomplete sessions
- Session list filter: add date filter and "needs review" default to existing /sessions route

</code_context>

<specifics>
## Specific Ideas

- The dentist goes room-to-room: record patient A, hit "Next Patient", immediately starts recording patient B. No waiting for extraction. Notes are written batch-style at end of day or during a break.
- Auto-pause is a safety net, not the primary workflow mechanism. "Next Patient" is always explicit.
- "Listening..." (amber) communicates that the system is still paying attention during auto-pause — not the same as "Paused" (gray) which is a manual action.
- Warn only, never block: the patient is sitting in the chair. Recording with degraded quality beats not recording at all. Missing mic is the sole exception.
- Health check includes network connectivity to other machines — forward-looking for Phase 6 split architecture where workstations talk to a GPU server.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-workflow-and-recovery*
*Context gathered: 2026-03-29*
