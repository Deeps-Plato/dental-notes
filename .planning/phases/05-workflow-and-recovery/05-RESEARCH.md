# Phase 5: Workflow and Recovery - Research

**Researched:** 2026-03-29
**Domain:** Session lifecycle orchestration -- batch multi-patient workflow, auto-pause/resume with rolling audio buffer, error recovery with retry logic, and system health monitoring
**Confidence:** HIGH

## Summary

Phase 5 extends four existing subsystems (SessionManager, SessionStore, VadDetector/AudioChunker, OllamaService) to support a full clinic day. The codebase is well-structured for these changes: the state machine in SessionManager needs one new state (AUTO_PAUSED), SessionStore needs a status extension and periodic auto-save, the VAD pipeline needs silence duration tracking for auto-pause, and the extraction pipeline needs retry wrappers. One new dependency is added: `tenacity>=9.1.0` for declarative retry logic with exponential backoff.

All four requirements (WRK-01 through WRK-04) build on existing patterns. The "Next Patient" flow is a stop-then-start sequence on the existing SessionManager, with extraction deferred to review time (already the default since Phase 4 moved template selection to review). Auto-pause adds an AUTO_PAUSED state to the existing state machine, driven by the VadDetector already in the processing loop. Error recovery wraps existing calls (extraction, transcription, mic open) with tenacity decorators. The health endpoint aggregates checks that already exist in OllamaService (is_available, is_model_ready) with new GPU and mic checks.

The critical design insight from CONTEXT.md: auto-pause continuously captures audio into a rolling buffer even when "paused", so no speech is missed at patient transitions. This means AUTO_PAUSED does NOT stop AudioCapture -- it only stops feeding audio to the chunker/transcriber, while keeping a rolling buffer of the last N seconds. When speech is detected, the buffer contents are replayed into the chunker before resuming normal flow.

**Primary recommendation:** Implement in three work streams: (1) "Next Patient" flow + session list filtering + periodic auto-save, (2) auto-pause state machine + rolling buffer, (3) error recovery retry wrappers + health endpoint + UI status bar. These can be planned as 2-3 sequential plans with clear interfaces.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- "Next Patient" button: stops current session, auto-saves, starts new recording immediately -- no extraction delay between patients
- Extraction happens later during review, not at patient transition (keeps transitions fast)
- No explicit "Start Day" / "End Day" ceremony -- sessions are independent, UI groups them by date automatically
- End-of-day review: existing session list page defaults to today's sessions with a "needs review" filter (no new dedicated page)
- Template selection at review time (consistent with Phase 4 decision) -- "Next Patient" just starts recording
- Rolling audio buffer kept during auto-pause -- system continuously captures audio even when "paused"
- When VAD detects speech, rolling buffer (last 5-10 seconds) included so first sentence isn't clipped
- Auto-pause never triggers "Next Patient" -- patient transitions are always manual button press
- Visual states: Recording = green pulsing dot + "Recording", Auto-paused = amber dot + "Listening...", Manual pause = gray "Paused"
- Extraction failures: auto-retry 3 attempts with backoff, non-blocking banner, manual retry button if all fail
- Mic disconnect: immediately auto-save transcript, show prominent alert, dentist decides next step
- Whisper GPU OOM: buffer audio and retry after delay; if repeated, temporarily save raw audio until Whisper recovers
- Hard crash recovery: periodic auto-save of transcript chunks to disk (every N chunks or 30 seconds), detect incomplete sessions on restart
- Health endpoint: /api/health returning JSON status of all monitored components
- UI status bar: persistent bar with green/red indicators, polled every 30 seconds
- Monitored components: GPU, Ollama, mic, disk space, network connectivity
- Warn only, never block recording (except missing mic)
- Refresh rate: every 30 seconds via background polling

### Claude's Discretion
- Exact silence threshold default for auto-pause (configurable in settings)
- Rolling buffer size (5 vs 10 seconds)
- Auto-save frequency for crash recovery (every N chunks or time-based)
- Retry backoff timing for extraction failures
- Health status bar visual design and placement
- How network connectivity check works for multi-machine monitoring
- Incomplete session detection and resume/finalize UX on restart

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WRK-01 | Batch session management -- multi-patient day mode with "Next Patient" flow and end-of-day review queue | SessionManager stop/start sequence, SessionStore already persists sessions, session list filtering by date/status, "Next Patient" route |
| WRK-02 | Auto-pause on extended silence with auto-resume on speech -- system always listens even when paused | New AUTO_PAUSED state in SessionManager, VadDetector silence tracking, rolling audio buffer in AudioCapture/AudioChunker, visual state indicators |
| WRK-03 | Error recovery -- retry logic for Ollama/GPU/mic failures with graceful degradation; session data never lost on crash | tenacity retry decorators on extraction/transcription, periodic auto-save via TranscriptWriter/SessionStore, mic disconnect detection, incomplete session recovery on startup |
| WRK-04 | Health check endpoint reporting GPU status, Ollama reachability, mic availability | New /api/health route, torch.cuda checks, OllamaService.is_available(), sounddevice device enumeration, shutil.disk_usage(), HTMX-polled status bar |
</phase_requirements>

## Standard Stack

### Core (already installed, no changes)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.135.0 | /api/health endpoint, "Next Patient" route, status bar polling | Already in use for all routes |
| Jinja2 | >=3.1.0 | Status bar partial, auto-pause indicator, session list date filter | Already in use for all templates |
| HTMX | 2.0.4 | Polling health status bar (hx-trigger="every 30s"), Next Patient button | Already loaded in index.html |
| sse-starlette | >=2.0.0 | Auto-pause/resume state changes streamed to browser | Already in use for transcript SSE |
| sounddevice | >=0.5.0 | Mic availability check, disconnect detection via PortAudioError | Already in use for AudioCapture |
| silero-vad | >=5.1 | Extended silence detection for auto-pause threshold | Already in use via VadDetector |
| Pydantic | (via pydantic-settings) | SessionStatus extension, health check response models | Already in use for all models |

### New Addition
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tenacity | >=9.1.0 | Retry with exponential backoff for extraction/transcription failures | Standard Python retry library. Declarative decorator API. Supports custom exception filtering, before_sleep callbacks for logging/notification, stop_after_attempt. Already recommended in project STACK.md research. |

### No New Dependencies Needed For
| Capability | Why No New Dep |
|------------|----------------|
| GPU status check | `torch.cuda.is_available()` and `torch.cuda.get_device_properties()` -- torch is already installed via faster-whisper/silero-vad |
| Disk space check | `shutil.disk_usage()` -- stdlib since Python 3.3 |
| Ollama health | `OllamaService.is_available()` and `is_model_ready()` already exist |
| Auto-pause state machine | Pure application logic extending existing SessionManager |
| Rolling audio buffer | Pure numpy/collections.deque in existing AudioCapture |
| Periodic auto-save | Existing TranscriptWriter.append() with fsync + SessionStore._write() |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | Manual retry loop (stdlib) | tenacity is cleaner for 3+ retry scenarios with backoff, jitter, and exception filtering. Manual loops get messy fast. |
| shutil.disk_usage | psutil.disk_usage | psutil adds a dependency for identical functionality. shutil is stdlib. |
| GPUtil | torch.cuda | GPUtil calls nvidia-smi subprocess. torch.cuda is already imported and provides the same info programmatically. |
| HTMX polling | WebSocket | HTMX polling every 30s is simpler and matches existing patterns. WebSocket adds complexity for a 30s update. |

**Installation:**
```bash
pip install "tenacity>=9.1.0"
```

Add to pyproject.toml dependencies:
```toml
"tenacity>=9.1.0",
```

## Architecture Patterns

### State Machine Extension

The existing SessionManager state machine:
```
IDLE -> RECORDING -> PAUSED -> RECORDING -> STOPPING -> IDLE
```

Extended for Phase 5:
```
IDLE -> RECORDING -> AUTO_PAUSED -> RECORDING -> STOPPING -> IDLE
           |              ^                         ^
           v              |                         |
         PAUSED -> RECORDING -----------------------+
           |
           v
        STOPPING -> IDLE
```

**Key difference between PAUSED and AUTO_PAUSED:**
- `PAUSED` (manual): AudioCapture.stop() called. No audio captured. Gray "Paused" indicator.
- `AUTO_PAUSED`: AudioCapture continues running. Audio goes into rolling buffer (NOT chunker). VadDetector monitors for speech. Amber "Listening..." indicator.

### Rolling Audio Buffer Pattern

```python
# In the processing loop (background thread):
if self._state == SessionState.AUTO_PAUSED:
    block = self._capture.get_block()
    if block is None:
        continue
    # Feed to rolling buffer (circular, fixed size)
    self._rolling_buffer.append(block)
    # Check if speech has returned
    if self._vad.is_speech(block):
        self._speech_detected_count += 1
        if self._speech_detected_count >= SPEECH_CONFIRM_BLOCKS:
            # Replay rolling buffer into chunker, then resume
            self._replay_rolling_buffer()
            self._transition_to_recording()
    else:
        self._speech_detected_count = 0
    continue
```

The rolling buffer is a `collections.deque(maxlen=N)` of numpy arrays. At 16kHz with 1600-sample blocks (100ms each), a 10-second buffer is `deque(maxlen=100)`. Memory cost: 100 * 1600 * 4 bytes = ~640KB. Negligible.

### "Next Patient" Flow

```
User clicks "Next Patient"
  -> POST /session/next-patient
    -> SessionManager.stop()           # Finalizes current transcript
    -> SessionStore.create_session()   # Persists with RECORDED status
    -> SessionManager.start()          # Starts new recording immediately
    -> Return HTMX partial (recording state, transcript cleared)
```

Extraction is NOT triggered. Session is saved with status RECORDED. The dentist reviews and extracts at end of day. This keeps patient transitions under 1 second (no GPU handoff needed).

### Periodic Auto-Save Pattern

```python
# In the processing loop, after each successful transcription:
self._chunks_since_save += 1
now = time.monotonic()
if (self._chunks_since_save >= AUTO_SAVE_CHUNK_THRESHOLD
        or now - self._last_auto_save >= AUTO_SAVE_INTERVAL_SECS):
    self._auto_save()
    self._chunks_since_save = 0
    self._last_auto_save = now
```

Auto-save writes a partial session JSON to a well-known path (`sessions/_incomplete_{session_id}.json`). On startup, the app scans for `_incomplete_*.json` files and offers to resume or finalize them.

### Error Recovery with tenacity

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ValueError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _extract_with_retry(self, transcript: str, whisper_service, template_type=None):
    return self.extract_with_gpu_handoff(transcript, whisper_service, template_type)
```

For mic disconnect, tenacity is NOT used. Instead, the processing loop catches `PortAudioError` and transitions to an error state with the transcript already saved (periodic auto-save guarantees this).

### Health Check Endpoint Pattern

```python
@router.get("/api/health")
async def health_check(request: Request):
    """System health status for all monitored components."""
    checks = {}

    # GPU
    try:
        import torch
        checks["gpu"] = {
            "available": torch.cuda.is_available(),
            "name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "memory_total_mb": round(torch.cuda.get_device_properties(0).total_mem / 1e6)
                if torch.cuda.is_available() else None,
        }
    except Exception:
        checks["gpu"] = {"available": False, "error": "torch.cuda unavailable"}

    # Ollama
    ollama_service = request.app.state.clinical_extractor._ollama if ... else None
    checks["ollama"] = {
        "reachable": ollama_service.is_available() if ollama_service else False,
        "model_ready": ollama_service.is_model_ready() if ollama_service else False,
    }

    # Microphone
    try:
        from dental_notes.audio.capture import list_input_devices
        devices = list_input_devices()
        checks["microphone"] = {"available": len(devices) > 0, "device_count": len(devices)}
    except Exception:
        checks["microphone"] = {"available": False, "error": "sounddevice unavailable"}

    # Disk space
    import shutil
    usage = shutil.disk_usage(request.app.state.settings.storage_dir)
    checks["disk"] = {
        "free_gb": round(usage.free / 1e9, 1),
        "total_gb": round(usage.total / 1e9, 1),
        "warning": usage.free < 1e9,  # Warn if < 1GB free
    }

    # Overall status
    ok = (checks["gpu"]["available"]
          and checks["ollama"]["reachable"]
          and checks["microphone"]["available"]
          and not checks["disk"]["warning"])

    return JSONResponse(content={"status": "ok" if ok else "degraded", "checks": checks})
```

### Recommended Project Structure Changes

```
src/dental_notes/
  session/
    manager.py          # ADD: AUTO_PAUSED state, rolling buffer, auto-pause logic,
                        #      periodic auto-save, "next patient" method
    store.py            # ADD: INCOMPLETE status, incomplete session scan,
                        #      date/status filtering for list_sessions()
    transcript_writer.py  # No changes (already crash-safe with fsync)
  audio/
    capture.py          # Minor: mic availability check method
    vad.py              # No changes (already provides is_speech/get_speech_probability)
  clinical/
    extractor.py        # ADD: retry wrapper around extract_with_gpu_handoff
    ollama_service.py   # No changes (is_available/is_model_ready already exist)
  ui/
    routes.py           # ADD: /session/next-patient, /api/health,
                        #      session list date filter, auto-pause status in SSE
  health.py             # NEW: HealthChecker class aggregating all component checks
  config.py             # ADD: auto_pause_silence_secs, rolling_buffer_secs,
                        #      auto_save_interval_secs, extraction_max_retries
  templates/
    _session.html       # ADD: "Next Patient" button, auto-pause indicator
    _health_bar.html    # NEW: status bar partial for HTMX polling
    index.html          # ADD: health status bar section
    sessions.html       # ADD: date filter, "needs review" default filter
  static/
    style.css           # ADD: auto-pause amber indicator, health status bar,
                        #      "Next Patient" button styling
```

### Anti-Patterns to Avoid
- **Blocking the asyncio loop for health checks:** GPU/Ollama checks can be slow (~100ms). Run them in thread pool executor, or cache results with a 30-second TTL (since the UI polls every 30s anyway).
- **Stopping AudioCapture during auto-pause:** The whole point of auto-pause is continuous listening. If you stop the stream, you lose audio. Only manual PAUSED stops the stream.
- **Triggering extraction on "Next Patient":** Extraction takes 10-30 seconds (GPU handoff). The dentist is walking to the next room. Defer extraction to review time.
- **Rolling buffer memory leak:** Use `collections.deque(maxlen=N)`, not an unbounded list. The buffer should never grow beyond the configured size.
- **Retry on permanent failures:** tenacity should only retry transient errors (ConnectionError, TimeoutError, CUDA OOM). Do NOT retry ValueError from bad LLM JSON (that will keep producing the same bad output).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Manual while loops with sleep | tenacity decorators | Edge cases: jitter, exception filtering, max delay caps, logging, async support. Manual loops miss these. |
| Disk space checking | os.statvfs + manual math | shutil.disk_usage() | Cross-platform, returns named tuple, no math needed. |
| GPU memory query | subprocess nvidia-smi parsing | torch.cuda.get_device_properties() | Already have torch. Parsing nvidia-smi output is fragile across driver versions. |
| Circular buffer | list with manual index wrapping | collections.deque(maxlen=N) | deque automatically evicts oldest items. Thread-safe for append/popleft. |
| Periodic task scheduling | threading.Timer chains | Simple counter in existing processing loop | Timer chains are error-prone. The processing loop already runs continuously -- just add a time check. |

**Key insight:** Phase 5 is primarily application logic built on existing infrastructure. The only new external tool is tenacity for retry. Everything else is stdlib (shutil, collections.deque) or already-installed libraries (torch.cuda, sounddevice).

## Common Pitfalls

### Pitfall 1: Rolling Buffer Replay Creates Duplicate Transcription
**What goes wrong:** When auto-pause ends, the rolling buffer is replayed into the chunker. If the buffer overlaps with audio already transcribed before auto-pause, you get duplicate text.
**Why it happens:** The chunker has overlap logic, but the rolling buffer may contain audio from before the silence gap.
**How to avoid:** Clear the rolling buffer at the START of auto-pause (not at resume). The buffer should only contain audio captured DURING auto-pause. The chunker's existing overlap deduplication handles the seam.
**Warning signs:** Repeated phrases at patient transition boundaries.

### Pitfall 2: Auto-Pause Triggers During Normal Conversation Pauses
**What goes wrong:** Dentist pauses to examine the patient for 30 seconds. System auto-pauses. When dentist speaks again, there's a visual state flicker.
**Why it happens:** Silence threshold too short.
**How to avoid:** Default auto-pause threshold should be 45-60 seconds (not 10-20). Normal conversation pauses are 5-15 seconds. Between-patient silence is 2-5 minutes. A 60-second threshold cleanly separates the two.
**Warning signs:** Frequent amber "Listening..." flickers during normal recording.

### Pitfall 3: Thread Safety in State Transitions
**What goes wrong:** Auto-pause transition triggered by background thread while UI route is processing a manual pause/stop request.
**Why it happens:** Auto-pause detection runs in the processing thread; UI actions come from asyncio routes.
**How to avoid:** All state transitions go through `with self._lock:`. The existing pattern already does this. Extend it consistently to AUTO_PAUSED transitions.
**Warning signs:** Occasional RuntimeError on invalid state transitions.

### Pitfall 4: Health Check Blocks Asyncio Event Loop
**What goes wrong:** /api/health calls `ollama_service.is_available()` which makes an HTTP request. If Ollama is slow or down, the entire web server hangs.
**Why it happens:** synchronous call in an async route without run_in_executor.
**How to avoid:** Either: (a) Run health checks in `asyncio.get_event_loop().run_in_executor()`, or (b) cache health results in a background thread that updates every 30 seconds, and the route just reads the cached result.
**Warning signs:** Web UI becomes unresponsive when Ollama is down.

### Pitfall 5: Incomplete Session Detection False Positives
**What goes wrong:** App crashes during normal session save. On restart, the incomplete session file exists alongside the completed session file.
**Why it happens:** Auto-save writes `_incomplete_{id}.json`. Normal save writes `{id}.json`. If crash happens between auto-save and normal save, both exist.
**How to avoid:** When creating a completed session, delete the corresponding `_incomplete_` file. On startup, only show incomplete sessions that do NOT have a corresponding completed session file.
**Warning signs:** Duplicate sessions in the review list after restart.

### Pitfall 6: Mic Disconnect Detection Lag
**What goes wrong:** USB mic unplugged. AudioCapture callback stops getting called, but no exception is raised immediately.
**Why it happens:** sounddevice/PortAudio may not raise an immediate error on USB disconnect. The stream callback simply stops firing.
**How to avoid:** Monitor audio block arrival rate. If no blocks arrive for N seconds (e.g., 5 seconds) while in RECORDING state, treat as mic disconnect. This is more reliable than waiting for PortAudioError.
**Warning signs:** Silent recording gap with no error message.

## Code Examples

### SessionState Extension
```python
# Source: Extending existing dental_notes/session/manager.py
class SessionState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    AUTO_PAUSED = "auto_paused"  # NEW: listening but not transcribing
    STOPPING = "stopping"
```

### Settings Extension
```python
# Source: Extending existing dental_notes/config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Auto-pause
    auto_pause_silence_secs: float = 60.0  # Silence before auto-pause
    rolling_buffer_secs: float = 10.0       # Rolling buffer duration
    auto_pause_enabled: bool = True          # Can be disabled in settings

    # Auto-save (crash recovery)
    auto_save_interval_secs: float = 30.0   # Time between auto-saves
    auto_save_chunk_threshold: int = 5       # Chunks between auto-saves

    # Retry
    extraction_max_retries: int = 3
    extraction_retry_base_delay: float = 2.0  # Seconds, exponential backoff
```

### SessionStatus Extension
```python
# Source: Extending existing dental_notes/session/store.py
class SessionStatus(str, Enum):
    INCOMPLETE = "incomplete"  # NEW: auto-saved, not properly stopped
    RECORDED = "recorded"
    EXTRACTED = "extracted"
    REVIEWED = "reviewed"
```

### "Next Patient" Route
```python
# Source: New route in dental_notes/ui/routes.py
@router.post("/session/next-patient", response_class=HTMLResponse)
async def session_next_patient(request: Request):
    """Stop current session, save, and immediately start a new recording."""
    session_manager = _get_session_manager(request)
    session_store = _get_session_store(request)

    # Stop current session (fast -- no extraction)
    try:
        transcript_path = session_manager.stop()
        chunks = session_manager.get_chunks()
        session_store.create_session(
            chunks=chunks,
            transcript_path=str(transcript_path),
        )
    except RuntimeError:
        pass  # No active session to stop -- just start fresh

    # Start new session immediately
    try:
        session_manager.start()
    except Exception as e:
        logger.exception("Failed to start new session after Next Patient")
        return _render_session_response(
            request, "idle", error=f"Could not start recording: {e}",
        )

    return _render_session_response(
        request, session_manager.get_state().value,
    )
```

### Extraction Retry Wrapper
```python
# Source: New wrapper in dental_notes/clinical/extractor.py
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

def _is_retryable(exc: BaseException) -> bool:
    """Determine if an extraction error is worth retrying."""
    retryable_types = (ConnectionError, TimeoutError, OSError)
    if isinstance(exc, retryable_types):
        return True
    # CUDA OOM errors surface as RuntimeError with specific messages
    if isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower():
        return True
    return False

# Used as: extract_with_retry = _make_retry_extractor(extractor, settings)
def create_retry_extract(extractor, settings):
    @retry(
        stop=stop_after_attempt(settings.extraction_max_retries),
        wait=wait_exponential(
            multiplier=settings.extraction_retry_base_delay,
            min=2,
            max=30,
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, RuntimeError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _extract(transcript, whisper_service, template_type=None):
        return extractor.extract_with_gpu_handoff(
            transcript, whisper_service, template_type=template_type
        )
    return _extract
```

### Rolling Buffer Implementation
```python
# Source: New code in dental_notes/session/manager.py
from collections import deque

# In SessionManager.__init__:
self._rolling_buffer: deque[np.ndarray] = deque(
    maxlen=int(settings.rolling_buffer_secs * settings.sample_rate / BLOCK_SIZE)
)
# 10 seconds at 16kHz / 1600 samples per block = 100 blocks
# Memory: 100 * 1600 * 4 bytes = 640KB

# In the processing loop when AUTO_PAUSED:
def _process_auto_paused(self, block: np.ndarray) -> None:
    """During auto-pause: buffer audio, monitor for speech."""
    self._rolling_buffer.append(block)
    if self._vad.is_speech(block):
        self._speech_resume_count += 1
        if self._speech_resume_count >= 3:  # 3 consecutive speech blocks = 300ms
            self._resume_from_auto_pause()
    else:
        self._speech_resume_count = 0

def _resume_from_auto_pause(self) -> None:
    """Replay rolling buffer into chunker, transition to RECORDING."""
    with self._lock:
        # Feed buffered audio to chunker so first words aren't lost
        for buffered_block in self._rolling_buffer:
            self._chunker.feed(buffered_block)
        self._rolling_buffer.clear()
        self._state = SessionState.RECORDING
        self._silence_duration = 0.0
        logger.info("Auto-pause ended: speech detected, resuming recording")
```

### Health Checker Class
```python
# Source: New file dental_notes/health.py
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ComponentHealth:
    name: str
    healthy: bool
    details: dict


class HealthChecker:
    """Aggregates health checks for all system components."""

    def __init__(self, settings, ollama_service=None):
        self._settings = settings
        self._ollama = ollama_service

    def check_gpu(self) -> ComponentHealth:
        try:
            import torch
            available = torch.cuda.is_available()
            details = {"available": available}
            if available:
                props = torch.cuda.get_device_properties(0)
                details["name"] = props.name
                details["total_memory_mb"] = round(props.total_mem / 1e6)
                details["allocated_mb"] = round(
                    torch.cuda.memory_allocated(0) / 1e6
                )
            return ComponentHealth("gpu", available, details)
        except Exception as e:
            return ComponentHealth("gpu", False, {"error": str(e)})

    def check_ollama(self) -> ComponentHealth:
        if self._ollama is None:
            return ComponentHealth("ollama", False, {"error": "not configured"})
        reachable = self._ollama.is_available()
        model_ready = self._ollama.is_model_ready() if reachable else False
        return ComponentHealth(
            "ollama",
            reachable and model_ready,
            {"reachable": reachable, "model_ready": model_ready},
        )

    def check_microphone(self) -> ComponentHealth:
        try:
            from dental_notes.audio.capture import list_input_devices
            devices = list_input_devices()
            return ComponentHealth(
                "microphone",
                len(devices) > 0,
                {"device_count": len(devices)},
            )
        except Exception as e:
            return ComponentHealth("microphone", False, {"error": str(e)})

    def check_disk(self) -> ComponentHealth:
        usage = shutil.disk_usage(self._settings.storage_dir)
        free_gb = round(usage.free / 1e9, 1)
        return ComponentHealth(
            "disk",
            free_gb >= 1.0,
            {
                "free_gb": free_gb,
                "total_gb": round(usage.total / 1e9, 1),
                "warning": free_gb < 1.0,
            },
        )

    def check_all(self) -> dict:
        checks = [
            self.check_gpu(),
            self.check_ollama(),
            self.check_microphone(),
            self.check_disk(),
        ]
        all_healthy = all(c.healthy for c in checks)
        return {
            "status": "ok" if all_healthy else "degraded",
            "checks": {c.name: {"healthy": c.healthy, **c.details} for c in checks},
        }
```

### Date-Filtered Session List
```python
# Source: Extending dental_notes/session/store.py
from datetime import date

def list_sessions(
    self,
    filter_date: date | None = None,
    filter_status: SessionStatus | None = None,
) -> list[SavedSession]:
    """Return sessions, optionally filtered by date and/or status."""
    sessions: list[SavedSession] = []
    for json_path in self._sessions_dir.glob("*.json"):
        # Skip incomplete session files
        if json_path.name.startswith("_incomplete_"):
            continue
        data = json.loads(json_path.read_text(encoding="utf-8"))
        session = SavedSession.model_validate(data)

        # Apply filters
        if filter_date and session.created_at.date() != filter_date:
            continue
        if filter_status and session.status != filter_status:
            continue

        sessions.append(session)

    sessions.sort(key=lambda s: s.created_at, reverse=True)
    return sessions
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual retry loops | tenacity decorators | tenacity 9.x (2025-2026) | Cleaner retry logic with built-in backoff, jitter, logging |
| GPUtil + nvidia-smi | torch.cuda API directly | PyTorch 2.x | No subprocess spawning, no output parsing, works when nvidia-smi not in PATH |
| os.statvfs (Unix only) | shutil.disk_usage (cross-platform) | Python 3.3+ | Works on Windows without psutil dependency |
| Separate health check library | FastAPI native route | Always available | No library needed for simple JSON endpoint |

**Deprecated/outdated:**
- GPUtil: Last updated 2023, uses subprocess nvidia-smi parsing. Use torch.cuda directly.
- retry (pip package): Unmaintained predecessor to tenacity. Use tenacity.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.2.0 + pytest-asyncio >=0.23.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x --tb=short` |
| Full suite command | `pytest tests/ --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WRK-01 | "Next Patient" stops session + saves + starts new | unit | `pytest tests/test_session_manager.py::TestNextPatient -x` | No -- Wave 0 |
| WRK-01 | Session list filters by date and status | unit | `pytest tests/test_session_store.py::TestSessionListFiltering -x` | No -- Wave 0 |
| WRK-01 | /session/next-patient route returns correct HTMX | unit | `pytest tests/test_routes.py::TestNextPatientRoute -x` | No -- Wave 0 |
| WRK-02 | AUTO_PAUSED state transition on extended silence | unit | `pytest tests/test_session_manager.py::TestAutoPause -x` | No -- Wave 0 |
| WRK-02 | Rolling buffer replays on speech detection | unit | `pytest tests/test_session_manager.py::TestRollingBuffer -x` | No -- Wave 0 |
| WRK-02 | Auto-pause visual states in SSE stream | unit | `pytest tests/test_routes.py::TestAutoPauseSSE -x` | No -- Wave 0 |
| WRK-03 | Extraction retries with backoff on failure | unit | `pytest tests/test_extractor.py::TestExtractionRetry -x` | No -- Wave 0 |
| WRK-03 | Periodic auto-save writes incomplete session | unit | `pytest tests/test_session_manager.py::TestAutoSave -x` | No -- Wave 0 |
| WRK-03 | Incomplete session detection on startup | unit | `pytest tests/test_session_store.py::TestIncompleteSessionRecovery -x` | No -- Wave 0 |
| WRK-03 | Mic disconnect triggers auto-save and error state | unit | `pytest tests/test_session_manager.py::TestMicDisconnect -x` | No -- Wave 0 |
| WRK-04 | /api/health returns GPU, Ollama, mic, disk status | unit | `pytest tests/test_health.py -x` | No -- Wave 0 |
| WRK-04 | Health status bar updates via HTMX polling | unit | `pytest tests/test_routes.py::TestHealthStatusBar -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --tb=short`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_health.py` -- covers WRK-04 (HealthChecker unit tests)
- [ ] `tests/test_session_manager.py::TestAutoPause` -- covers WRK-02 (auto-pause state transitions)
- [ ] `tests/test_session_manager.py::TestRollingBuffer` -- covers WRK-02 (buffer replay)
- [ ] `tests/test_session_manager.py::TestNextPatient` -- covers WRK-01 (next patient flow)
- [ ] `tests/test_session_manager.py::TestAutoSave` -- covers WRK-03 (periodic save)
- [ ] `tests/test_session_manager.py::TestMicDisconnect` -- covers WRK-03 (mic error handling)
- [ ] `tests/test_session_store.py::TestSessionListFiltering` -- covers WRK-01 (date/status filter)
- [ ] `tests/test_session_store.py::TestIncompleteSessionRecovery` -- covers WRK-03 (crash recovery)
- [ ] `tests/test_extractor.py::TestExtractionRetry` -- covers WRK-03 (retry with tenacity)
- [ ] `tests/test_routes.py::TestNextPatientRoute` -- covers WRK-01 (route test)
- [ ] `tests/test_routes.py::TestHealthStatusBar` -- covers WRK-04 (HTMX polling test)
- [ ] `tests/conftest.py` -- extend FakeSessionManager with AUTO_PAUSED state

## Open Questions

1. **Exact auto-pause silence threshold**
   - What we know: Normal conversation pauses are 5-15 seconds. Between-patient silence is 2-5 minutes. The user wants it configurable.
   - What's unclear: Whether 45s, 60s, or 90s is the right default.
   - Recommendation: Default to 60 seconds. This safely separates conversation pauses from patient transitions. Configurable via `DENTAL_AUTO_PAUSE_SILENCE_SECS` env var.

2. **Rolling buffer size: 5 vs 10 seconds**
   - What we know: Buffer must include enough pre-speech audio to not clip the first sentence. Typical sentence onset is ~0.5-1s.
   - What's unclear: How much "ramp-up" audio (e.g., patient entering room, greeting) is useful.
   - Recommendation: Default to 10 seconds. Memory cost is trivial (~640KB). Better to have too much buffer than too little. The first few seconds often contain greetings that help the LLM re-attribute speakers.

3. **Network connectivity check for Phase 6 split architecture**
   - What we know: Phase 6 adds multi-machine support. Health check should forward-plan for this.
   - What's unclear: No split architecture exists yet; no target machines to check.
   - Recommendation: Add a placeholder `check_network()` method that returns healthy=True with a note "split architecture not configured". Phase 6 will fill it in. Keep the health check extensible.

4. **Incomplete session UX on restart**
   - What we know: After crash, incomplete sessions need to be surfaced to the user.
   - What's unclear: Should incomplete sessions appear in the normal session list, or in a separate "Recovery" prompt on startup?
   - Recommendation: Show them in the normal session list with an "Incomplete" status badge (amber). Add a banner at the top of the session list page: "N incomplete sessions found from previous run" when any exist. No separate recovery page needed.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `session/manager.py`, `session/store.py`, `audio/vad.py`, `audio/capture.py`, `clinical/extractor.py`, `clinical/ollama_service.py`, `ui/routes.py`, `config.py`, `main.py` -- all read and analyzed
- Project STACK.md research (`.planning/research/STACK.md`) -- tenacity recommendation, retry patterns, batch workflow design
- Phase 4 RESEARCH.md -- established patterns for extending existing subsystems

### Secondary (MEDIUM confidence)
- [tenacity docs](https://tenacity.readthedocs.io/) -- retry patterns, exponential backoff, before_sleep callbacks
- [PyTorch CUDA docs](https://docs.pytorch.org/docs/stable/cuda.html) -- `torch.cuda.is_available()`, `get_device_properties()`, `memory_allocated()`
- [python-sounddevice docs](https://python-sounddevice.readthedocs.io/) -- CallbackFlags, PortAudioError, device enumeration
- [Ollama API docs](https://github.com/ollama/ollama/blob/main/docs/api.md) -- /api/tags, health check via root endpoint
- [shutil.disk_usage](https://docs.python.org/3/library/shutil.html#shutil.disk_usage) -- stdlib disk space checking

### Tertiary (LOW confidence)
- Web search: sounddevice mic disconnect detection -- PortAudio does not reliably raise exceptions on USB disconnect. Monitoring block arrival rate is the recommended workaround (needs validation on target hardware).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- tenacity is the only new dep, already validated in project STACK.md
- Architecture: HIGH -- all patterns extend existing code with well-understood state machine additions
- Pitfalls: HIGH -- identified from deep codebase analysis + known sounddevice/PortAudio limitations
- Validation: HIGH -- test map covers all requirements, test framework already configured

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable domain -- no fast-moving dependencies)
