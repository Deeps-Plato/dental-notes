# Phase 1: Streaming Capture and Transcription - Research

**Researched:** 2026-03-06
**Domain:** Real-time audio capture, VAD-driven chunking, local GPU transcription (faster-whisper)
**Confidence:** HIGH

## Summary

Phase 1 delivers a streaming audio capture and transcription pipeline: mic audio flows through sounddevice into a thread-safe queue, silero-vad detects speech boundaries and skips noise-only chunks, faster-whisper transcribes each speech chunk on the local GPU, and the transcript accumulates in a plain text file. A FastAPI + HTMX web UI provides start/stop/pause controls and shows the transcript growing via Server-Sent Events. A keyboard shortcut provides an alternative start/stop mechanism.

The proven pattern from `whisper-ptt/ptt.py` (sounddevice callback -> audio queue -> silero-vad -> faster-whisper) transfers directly. The critical difference is the target hardware floor: GTX 1050 with 4GB VRAM has compute capability 6.1, which does NOT support native float16 on CTranslate2 -- `compute_type="int8"` is the correct choice for this GPU class. The existing v1 backend code uses `float16` (likely running on a higher-capability GPU), so this must be changed. The `small` model with int8 quantization fits comfortably in 4GB VRAM (~500MB) and provides the best accuracy-to-resource tradeoff for this constraint.

**Primary recommendation:** Use `WhisperModel("small", device="cuda", compute_type="int8")` with silero-vad pre-filtering and ~1s overlap chunking. Build a fresh v2 FastAPI app (not extending the v1 backend) with HTMX SSE for real-time transcript display.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hybrid chunking: VAD-driven silence detection to find natural speech boundaries, with a maximum duration cap to force a cut during continuous speech
- Skip chunks where VAD detects no speech -- do not send noise-only audio to Whisper (prevents hallucinations on dental equipment noise like suction, handpieces, ultrasonic scalers)
- Overlap chunks by ~1 second at boundaries to prevent word splitting across chunk edges
- Auto-deduplicate repeated words in the overlap region when stitching chunk transcripts together
- Show a basic audio level indicator in the UI so the dentist can confirm the mic is picking up speech
- Start and stop via both a browser button (FastAPI + HTMX web UI) and a keyboard shortcut
- Pause and resume supported within a single session (e.g. dentist steps out, takes a phone call)
- Transcript saved to a text file automatically when the session is stopped
- No live transcript display during the procedure (out of scope per requirements) -- the dentist sees text accumulating as confirmation it's working
- Universal tooth numbering system (1-32) -- US standard
- Full-service practice vocabulary covering: restorative, perio, endo, oral surgery, implants, prosthetics, orthodontics, cosmetics, sleep apnea
- Specific brand names for Whisper initial_prompt: Shofu, Ivoclar, Filtek, RelyX, Gluma
- Mix of full surface names and abbreviations (MOD, DO, BL) in prompt
- CDT code format awareness (D####)
- Plain text (.txt) format -- no JSON, no structured metadata
- No timestamps under normal operation
- User-configurable storage folder
- Append each chunk's transcript to the file for crash safety

### Claude's Discretion
- Maximum chunk duration before forced cut (balance VRAM usage on GTX 1050 vs. Whisper accuracy with longer context)
- Silence gap threshold for VAD-driven chunk boundaries (tune for dental conversation cadence)
- Crash recovery strategy (flush-per-chunk vs. periodic flush -- leaning flush-per-chunk for reliability)
- Transcript file naming convention (date-time based, no patient info, privacy-safe)
- Whisper model size selection within GTX 1050 4GB VRAM constraint
- Keyboard shortcut key choice for start/stop/pause

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUD-01 | User can start and stop a streaming capture session that records audio in small chunks, transcribes each chunk immediately, and discards the audio -- no full-length recording is ever stored | sounddevice InputStream callback + audio queue pattern from ptt.py; VAD-driven chunk boundaries; append-to-file then discard audio buffer |
| TRX-01 | Audio chunks are transcribed locally using faster-whisper on NVIDIA GPU, with a model small enough to run on GTX 1050 (4GB VRAM) | `WhisperModel("small", device="cuda", compute_type="int8")` fits in ~500MB VRAM on CC 6.1 GPUs; int8 is the only efficient quantization for GTX 1050 |
| TRX-02 | Transcription uses a dental terminology vocabulary prompt for accuracy | `initial_prompt` parameter with comprehensive dental vocabulary (teeth 1-32, procedures, materials, brand names, CDT codes) |
| PRV-01 | All processing runs locally -- no patient data transmitted over the internet | FastAPI bound to localhost only; no external API calls; Whisper model loaded locally; no telemetry |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | >=1.0.3 | Local speech-to-text via CTranslate2 | 4x faster than OpenAI whisper, lower VRAM, int8 quantization support |
| silero-vad | >=5.1 | Voice Activity Detection for chunk boundaries | Lightweight (no GPU needed), 0.004 RTF on CPU, proven in whisper-ptt |
| sounddevice | >=0.5.0 | Audio capture from microphone | PortAudio wrapper, callback-based InputStream, proven pattern in ptt.py |
| FastAPI | >=0.135.0 | Web server with SSE support | Built-in `EventSourceResponse` (no external SSE library needed), async |
| uvicorn | >=0.30.0 | ASGI server | Standard FastAPI deployment server |
| numpy | >=1.26.0 | Audio buffer manipulation | Required by sounddevice and faster-whisper for float32 audio arrays |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| jinja2 | >=3.1.0 | HTML template rendering for HTMX UI | FastAPI `Jinja2Templates` for the web interface |
| pydantic | >=2.7.0 | Config validation and API models | Settings management, request/response models |
| pydantic-settings | >=2.3.0 | Environment-based configuration | Load settings from `.env` or environment variables |
| torch | >=2.0.0 | PyTorch runtime (silero-vad dependency) | Required by silero-vad; CPU-only install sufficient for VAD |
| pynput | >=1.7.6 | Global keyboard shortcut listener | Start/stop/pause via keyboard shortcut alongside web UI |

### Frontend (CDN, no npm)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| htmx | 2.x | Hypermedia-driven UI updates | SSE extension for real-time transcript display |
| htmx-ext-sse | 2.x | SSE extension for htmx | `hx-ext="sse"` + `sse-connect` + `sse-swap` for streaming transcript |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| silero-vad | webrtcvad | silero-vad has higher accuracy (87.7% vs lower TPR), already proven in ptt.py |
| SSE (HTMX) | WebSocket | SSE is simpler (one-way server->client), works through proxies, HTMX has native extension |
| pynput | keyboard (library) | pynput already proven in ptt.py, handles global hotkeys on Windows |
| FastAPI SSE | sse-starlette | FastAPI 0.135.0+ has built-in SSE -- no external dependency needed |

**Installation:**
```bash
pip install faster-whisper>=1.0.3 silero-vad>=5.1 sounddevice>=0.5.0 numpy>=1.26.0
pip install "fastapi[standard]>=0.135.0" uvicorn>=0.30.0 pydantic-settings>=2.3.0 jinja2>=3.1.0
pip install pynput>=1.7.6
# PyTorch CPU-only (for silero-vad, not for Whisper -- Whisper uses CTranslate2 CUDA directly)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**CUDA/CTranslate2 Note:** faster-whisper bundles CTranslate2. Latest versions require CUDA 12 + cuDNN 9. For CUDA 11 + cuDNN 8, pin `ctranslate2<=3.24.0`. Verify with `nvidia-smi` on target machines.

## Architecture Patterns

### Recommended Project Structure
```
src/
  dental_notes/               # v2 package (separate from v1 backend)
    __init__.py
    config.py                  # pydantic-settings: model size, compute type, storage dir, etc.
    main.py                    # FastAPI app factory, lifespan (load whisper model)
    audio/
      __init__.py
      capture.py               # sounddevice InputStream, audio callback, queue management
      vad.py                   # silero-vad wrapper, speech detection, chunk boundary logic
    transcription/
      __init__.py
      whisper_service.py       # WhisperModel wrapper, transcribe(), dental prompt
      chunker.py               # Hybrid chunking logic: VAD boundaries + max duration cap
      stitcher.py              # Overlap deduplication when joining chunk transcripts
    session/
      __init__.py
      manager.py               # Session lifecycle: start, pause, resume, stop
      transcript_writer.py     # Append-to-file writer, flush-per-chunk, crash-safe
    ui/
      __init__.py
      routes.py                # FastAPI routes: session control + SSE transcript stream
      hotkey.py                # pynput keyboard shortcut listener (daemon thread)
    templates/
      index.html               # HTMX + SSE web interface
      _session.html             # Session controls partial
      _transcript.html          # Transcript display partial
    static/
      style.css                # Minimal styling
tests/
  test_vad.py
  test_chunker.py
  test_stitcher.py
  test_whisper_service.py
  test_session_manager.py
  test_transcript_writer.py
  conftest.py                  # Shared fixtures, mock audio data
```

### Pattern 1: Audio Pipeline (Producer-Consumer with Queue)
**What:** sounddevice callback produces audio blocks into a thread-safe queue; a consumer thread reads from the queue for VAD processing and chunking.
**When to use:** Always -- this is the core data flow pattern.
**Example:**
```python
# Source: whisper-ptt/ptt.py (proven pattern)
import queue
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK_SIZE = 1600  # 100ms at 16kHz
audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)

def audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
    """Called by sounddevice on each audio block. Must be non-blocking."""
    try:
        audio_q.put_nowait(indata.copy().flatten())
    except queue.Full:
        pass  # Drop chunk silently -- better than blocking the audio thread

stream = sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    blocksize=BLOCK_SIZE,
    callback=audio_callback,
    device=device_index,  # from sd.query_devices()
)
```

### Pattern 2: VAD-Driven Chunking with Overlap
**What:** Accumulate audio blocks. silero-vad processes 512-sample chunks to detect speech. When silence gap exceeds threshold, finalize the chunk. Add ~1s overlap from the start of the next chunk.
**When to use:** For creating natural speech boundary chunks to send to Whisper.
**Example:**
```python
# Discretion recommendation:
# - Max chunk duration: 20 seconds (stays well within 30s Whisper window,
#   uses ~10MB RAM per chunk at 16kHz float32)
# - Silence gap: 1.5 seconds (dental conversations have natural pauses
#   between instructions/observations)
# - Overlap: 1 second (16000 samples) at chunk boundaries

SILENCE_THRESHOLD_SECS = 1.5
MAX_CHUNK_DURATION_SECS = 20
OVERLAP_SAMPLES = 16000  # 1 second at 16kHz

def process_vad_chunk(audio_block: np.ndarray, vad_model) -> float:
    """Run silero-vad on 512-sample sub-chunks, return speech probability."""
    # silero-vad requires exactly 512 samples at 16kHz
    probs = []
    for i in range(0, len(audio_block) - 511, 512):
        chunk_512 = torch.from_numpy(audio_block[i:i+512])
        prob = vad_model(chunk_512, SAMPLE_RATE).item()
        probs.append(prob)
    return max(probs) if probs else 0.0
```

### Pattern 3: SSE Transcript Streaming
**What:** FastAPI SSE endpoint yields transcript updates as `ServerSentEvent` objects. HTMX SSE extension connects and swaps content.
**When to use:** For real-time transcript display in the web UI.
**Example:**
```python
# FastAPI side (built-in SSE, no external library)
from fastapi.sse import EventSourceResponse, ServerSentEvent
import asyncio

@app.get("/session/stream", response_class=EventSourceResponse)
async def stream_transcript():
    """SSE endpoint -- yields transcript chunks as they are transcribed."""
    async def event_generator():
        last_length = 0
        while session_manager.is_active():
            current = session_manager.get_transcript()
            if len(current) > last_length:
                new_text = current[last_length:]
                last_length = len(current)
                yield ServerSentEvent(
                    data=f"<div id='transcript' hx-swap-oob='beforeend'>{new_text}</div>",
                    event="transcript",
                )
            await asyncio.sleep(0.5)
        yield ServerSentEvent(data="", event="session_end")
    return event_generator()
```
```html
<!-- HTMX side -->
<div hx-ext="sse" sse-connect="/session/stream">
    <div id="transcript" sse-swap="transcript" hx-swap="beforeend"></div>
</div>
```

### Pattern 4: Flush-Per-Chunk Transcript Writing
**What:** Each transcribed chunk is immediately appended to the transcript file and flushed. If the process crashes, all previously transcribed chunks are preserved.
**When to use:** Always -- crash safety is critical for 20-30 minute appointments.
**Example:**
```python
# Discretion recommendation: flush-per-chunk (not periodic flush)
# Rationale: appointments are 10-30 min; losing even 1 min of transcript
# is unacceptable. Flush cost is negligible (one small string write per chunk).

class TranscriptWriter:
    def __init__(self, output_dir: Path):
        # Discretion: date-time naming, no patient info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = output_dir / f"session_{timestamp}.txt"
        self._file = open(self.path, "a", encoding="utf-8")

    def append(self, text: str) -> None:
        self._file.write(text)
        self._file.flush()
        os.fsync(self._file.fileno())  # force to disk

    def close(self) -> None:
        self._file.close()
```

### Pattern 5: Overlap Deduplication
**What:** When chunks overlap by ~1s, the same words may appear at the end of chunk N and the start of chunk N+1. Compare the tail of the previous transcript with the head of the new one to remove duplicates.
**When to use:** Every chunk boundary when stitching transcripts.
**Example:**
```python
from difflib import SequenceMatcher

def deduplicate_overlap(prev_text: str, new_text: str, max_overlap_words: int = 10) -> str:
    """Remove duplicated words at the boundary between two chunk transcripts."""
    prev_words = prev_text.split()
    new_words = new_text.split()

    if not prev_words or not new_words:
        return new_text

    # Compare tail of previous with head of new
    tail = prev_words[-max_overlap_words:]
    head = new_words[:max_overlap_words]

    # Find longest matching suffix of tail that matches prefix of head
    best_overlap = 0
    for length in range(1, min(len(tail), len(head)) + 1):
        if tail[-length:] == head[:length]:
            best_overlap = length

    if best_overlap > 0:
        return " ".join(new_words[best_overlap:])
    return new_text
```

### Anti-Patterns to Avoid
- **Storing full audio then transcribing:** Violates streaming architecture. Audio chunks must be discarded after transcription -- never accumulate a full WAV.
- **Running VAD on the GPU:** silero-vad runs on CPU. Loading it on GPU wastes VRAM that Whisper needs. Use `torch.device("cpu")` explicitly.
- **Using float16 compute_type on GTX 1050:** CC 6.1 does not support efficient float16 in CTranslate2. Use `int8` instead. float16 will either error or fall back to float32 (slower, more VRAM).
- **Blocking the sounddevice callback:** The audio callback runs on a PortAudio thread. Any blocking operation (file I/O, model inference, locks) will cause audio drops. Only `queue.put_nowait()`.
- **Running Whisper inference on the main asyncio thread:** Whisper inference is CPU/GPU-bound and takes 1-3 seconds. Run it in a background thread or via `asyncio.to_thread()` to avoid blocking the FastAPI event loop.
- **Sending noise-only audio to Whisper:** Causes hallucinations (Whisper generates phantom text on silence/noise). VAD pre-filtering is mandatory, not optional.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Voice Activity Detection | Custom energy-threshold silence detector | silero-vad | Energy threshold fails on dental drill noise (loud but not speech); VAD uses a neural network trained on speech patterns |
| Audio resampling | Manual numpy resampling | sounddevice `samplerate=16000` | PortAudio handles hardware resampling correctly; manual resampling introduces artifacts |
| Microphone enumeration | Platform-specific device listing | `sd.query_devices()` | Cross-platform, handles USB mics, returns device capabilities |
| Whisper model management | Custom model download/cache | faster-whisper auto-download | Models cached in `~/.cache/huggingface/` automatically on first use |
| SSE protocol implementation | Manual `text/event-stream` formatting | FastAPI `EventSourceResponse` | Built-in keep-alive pings, correct headers, reconnection support |
| Overlap deduplication | Character-level diff | Word-level suffix/prefix matching | Words are the natural unit for Whisper output; character-level is fragile with punctuation differences |

**Key insight:** The audio pipeline (capture -> VAD -> chunk -> transcribe) is a solved pattern in whisper-ptt. The v2 work is structuring it as a web-accessible service with session management, not reinventing the audio processing.

## Common Pitfalls

### Pitfall 1: Whisper Hallucination on Dental Equipment Noise
**What goes wrong:** Dental handpieces, suction, ultrasonic scalers produce loud continuous noise. Whisper hallucinates coherent-sounding but completely fabricated text on non-speech audio.
**Why it happens:** Whisper was trained to always produce output. Given noise, it generates plausible text rather than silence. Silero-vad has ~87.7% true positive rate -- some noise segments leak through.
**How to avoid:**
1. VAD pre-filter with threshold 0.5+ (skip chunks below threshold)
2. Enable faster-whisper's built-in `vad_filter=True` as a second safety net
3. Set `no_speech_threshold=0.6` in transcribe() to suppress low-confidence segments
4. Consider `log_prob_threshold=-1.0` to filter hallucinated segments with low log probability
**Warning signs:** Repeated identical phrases, text appearing during known silence periods, generic filler text unrelated to dental context.

### Pitfall 2: compute_type="float16" on GTX 1050
**What goes wrong:** CTranslate2 requires compute capability >= 7.0 for native float16. GTX 1050 has CC 6.1. The model either fails to load, or falls back to float32 silently (using more VRAM and running slower).
**Why it happens:** The v1 codebase and whisper-ptt both use `compute_type="float16"`, which works on newer GPUs. Copy-pasting this to GTX 1050 target hardware breaks.
**How to avoid:** Use `compute_type="int8"` for GTX 1050. int8 is supported on CC 6.1 and uses ~74% less memory than float32. Accuracy impact is negligible (<0.1% WER difference).
**Warning signs:** CTranslate2 warning about float16 not being efficient, unexpectedly high VRAM usage, slower-than-expected inference.

### Pitfall 3: Blocking the asyncio Event Loop with Whisper Inference
**What goes wrong:** Whisper transcription takes 1-5 seconds per chunk. If called directly in an async FastAPI route, the entire web server blocks -- no SSE updates, no new requests.
**Why it happens:** FastAPI runs on asyncio. CPU/GPU-bound work must be offloaded to threads.
**How to avoid:** Use `asyncio.to_thread(transcribe_chunk, audio)` or run transcription in a dedicated background thread with results posted to an asyncio Queue.
**Warning signs:** Web UI freezes during transcription, SSE connection drops, timeout errors.

### Pitfall 4: Audio Queue Overflow
**What goes wrong:** If the consumer (VAD + transcription) can't keep up with the producer (sounddevice callback at 16kHz), the queue fills up and audio is silently dropped.
**Why it happens:** Whisper transcription is slower than real-time on weak GPUs. Multiple chunks can queue up during long transcription runs.
**How to avoid:**
1. Queue maxsize=200 (same as ptt.py -- ~20 seconds of buffered audio)
2. Separate VAD processing from Whisper inference -- VAD runs fast on CPU, Whisper on GPU
3. Pipeline: audio -> queue -> VAD thread (fast) -> speech chunks -> transcription thread (slow)
**Warning signs:** Gaps in transcript, lost sentences, audio_callback seeing `queue.Full`.

### Pitfall 5: CUDA/CTranslate2 Version Mismatch
**What goes wrong:** Latest CTranslate2 (4.7.x) requires CUDA 12 + cuDNN 9. Dental office machines may have CUDA 11.
**Why it happens:** Office IT may not have updated GPU drivers recently.
**How to avoid:** Check `nvidia-smi` output on target machines. If CUDA 11, pin `ctranslate2<=3.24.0` in requirements. If CUDA 12 + cuDNN 8, pin `ctranslate2<=4.4.0`.
**Warning signs:** ImportError or RuntimeError on CTranslate2 import, "CUDA driver version is insufficient" errors.

### Pitfall 6: Keyboard Shortcut Listener Blocking on Windows
**What goes wrong:** pynput keyboard listener callbacks run on a system thread. Long-running operations in the callback freeze all keyboard input system-wide.
**Why it happens:** Windows hooks require quick callback returns.
**How to avoid:** Keyboard callbacks should only set flags or post events to a queue. All actual work (start/stop session) happens in separate threads. Same pattern as ptt.py.
**Warning signs:** System-wide keyboard input freezing briefly when pressing hotkeys.

## Code Examples

### Whisper Model Loading with Correct Compute Type
```python
# Source: CTranslate2 quantization docs + faster-whisper GitHub
from faster_whisper import WhisperModel

# Discretion recommendation: "small" model
# - tiny/base: ~1GB VRAM, lower accuracy on dental terminology
# - small: ~1GB VRAM with int8, best accuracy/resource balance for 4GB GPU
# - medium: ~2.5GB VRAM with int8, might work but leaves less headroom
# - large: too big for 4GB VRAM even with int8

model = WhisperModel(
    "small",           # Discretion: "small" over "base" for dental accuracy
    device="cuda",
    compute_type="int8",  # MUST be int8 for CC 6.1 (GTX 1050/1070 Ti)
)
```

### Dental Vocabulary Initial Prompt
```python
# Source: CONTEXT.md locked decisions + whisper-ptt INITIAL_PROMPT pattern
DENTAL_INITIAL_PROMPT = (
    "Dental clinical appointment transcription. "
    # Tooth numbering
    "Universal tooth numbering: teeth 1 through 32, tooth 1, tooth 14, tooth 19, tooth 30. "
    # Surface names and abbreviations
    "Mesial, occlusal, distal, buccal, lingual, facial, incisal. "
    "MOD, DO, BL, MO, OL, MODBL, MI, DI. "
    # Restorative
    "Composite, amalgam, crown, bridge, onlay, inlay, veneer, bonding, bleaching. "
    "E.max, zirconia, PFM, porcelain-fused-to-metal, lithium disilicate. "
    # Perio
    "Prophy, prophylaxis, SRP, scaling and root planing, pocket depth, bleeding on probing, BOP. "
    "Probing depths, gingival margin, recession, furcation, mobility. "
    # Endo
    "Pulpectomy, pulpotomy, access opening, working length, obturation, root canal, "
    "gutta-percha, endodontic. "
    # Oral surgery
    "Simple extraction, surgical extraction, bone grafting, socket preservation, sutures. "
    # Implants and prosthetics
    "Implant, implant crown, abutment, denture, partial denture, flipper, Invisalign. "
    # Materials and brands
    "Shofu, Ivoclar, Filtek, RelyX, Gluma, Dentsply, Kerr. "
    # CDT codes
    "CDT code D0120, D0150, D0220, D0330, D1110, D2391, D2740, D3330, D4341, D7210. "
    # Sleep apnea
    "Sleep apnea, mandibular advancement device, oral appliance. "
    # Clinical terms
    "Caries, cavity, abscess, periapical, radiolucency, calculus, plaque, gingivitis, "
    "periodontitis, occlusion, malocclusion, TMJ, bruxism, fluoride, sealant."
)
```

### Microphone Selection
```python
# Source: whisper-ptt/ptt.py find_device() pattern
import sounddevice as sd

def list_input_devices() -> list[dict]:
    """Return available input devices for UI selection."""
    devices = sd.query_devices()
    return [
        {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]

def find_device_by_name(name: str) -> int | None:
    """Find device index by partial name match (case-insensitive)."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if name.lower() in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    return None
```

### Session State Machine
```python
# Source: architectural pattern from ptt.py state machine
from enum import Enum
import threading

class SessionState(Enum):
    IDLE = "idle"              # No active session
    RECORDING = "recording"    # Actively capturing and transcribing
    PAUSED = "paused"          # Session paused (mic stopped, model stays loaded)
    STOPPING = "stopping"      # Finalizing last chunk, closing file

class SessionManager:
    def __init__(self):
        self._state = SessionState.IDLE
        self._lock = threading.Lock()
        self._transcript = ""
        self._writer: TranscriptWriter | None = None

    def start(self, mic_device: int, output_dir: Path) -> None:
        with self._lock:
            if self._state != SessionState.IDLE:
                raise RuntimeError(f"Cannot start: state is {self._state}")
            self._state = SessionState.RECORDING
            # ... initialize audio stream, VAD, transcript writer

    def pause(self) -> None:
        with self._lock:
            if self._state != SessionState.RECORDING:
                raise RuntimeError(f"Cannot pause: state is {self._state}")
            self._state = SessionState.PAUSED
            # ... stop audio stream, keep model loaded

    def resume(self) -> None:
        with self._lock:
            if self._state != SessionState.PAUSED:
                raise RuntimeError(f"Cannot resume: state is {self._state}")
            self._state = SessionState.RECORDING
            # ... restart audio stream

    def stop(self) -> Path:
        with self._lock:
            if self._state not in (SessionState.RECORDING, SessionState.PAUSED):
                raise RuntimeError(f"Cannot stop: state is {self._state}")
            self._state = SessionState.STOPPING
            # ... finalize last chunk, close file, return path
            self._state = SessionState.IDLE
            return self._writer.path
```

## Discretion Recommendations

Based on research, here are recommendations for the areas left to Claude's discretion:

| Area | Recommendation | Rationale |
|------|----------------|-----------|
| **Whisper model size** | `small` with `int8` | ~500MB VRAM, significantly better accuracy than `base` on medical terminology, fits comfortably in 4GB |
| **Max chunk duration** | 20 seconds | Well within Whisper's 30s window; longer context = better accuracy; 20s of 16kHz float32 = ~1.3MB RAM |
| **Silence gap threshold** | 1.5 seconds | Dental conversations have natural pauses between observations; shorter than ptt.py's 2.0s to be more responsive |
| **Crash recovery** | Flush-per-chunk with `os.fsync()` | Zero data loss on crash; write cost is negligible (~1KB per chunk); appointments are 10-30 min |
| **File naming** | `session_YYYYMMDD_HHMMSS.txt` | Privacy-safe (no patient info), sortable, human-readable |
| **Keyboard shortcut** | F9 (start/stop toggle), F8 (pause/resume) | F9 already familiar from ptt.py; F-keys don't conflict with Dentrix shortcuts |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI whisper (PyTorch) | faster-whisper (CTranslate2) | 2023 | 4x speed, 2-3x less VRAM |
| float16 everywhere | int8 quantization on older GPUs | CTranslate2 3.x+ | Enables GTX 1050 support with <0.1% accuracy loss |
| sse-starlette (external) | FastAPI built-in SSE | FastAPI 0.135.0 (2025) | No external dependency for SSE |
| silero-vad v4 | silero-vad v5 (pysilero-vad 3.3.0) | Feb 2026 | Improved accuracy, same API |
| Manual event stream formatting | `ServerSentEvent` class | FastAPI 0.135.0 | Type-safe SSE with auto keep-alive |
| Store full WAV then transcribe | Stream chunks, discard immediately | Architecture decision | Eliminates disk PHI footprint |

**Deprecated/outdated:**
- `whisper_streaming` (ufal): Being replaced by SimulStreaming -- but neither is needed here since we're doing chunk-based, not word-level streaming
- `sse-starlette`: No longer needed with FastAPI >= 0.135.0 built-in SSE
- `compute_type="float16"` on CC 6.1 GPUs: Was never officially supported, use `int8`

## Open Questions

1. **CTranslate2 CUDA version on target dental office machines**
   - What we know: Latest CTranslate2 requires CUDA 12 + cuDNN 9
   - What's unclear: What CUDA version is installed on the office GTX 1050 machines
   - Recommendation: First task should include a startup check that logs CUDA version and suggests correct ctranslate2 pin if needed. Consider adding a `check_gpu_compatibility()` function.

2. **Whisper `small` vs `base` accuracy on dental terminology**
   - What we know: `small` has better general WER than `base`; dental terminology benefits from initial_prompt
   - What's unclear: Actual accuracy difference in dental operatory with equipment noise
   - Recommendation: Default to `small` (configurable). The initial_prompt provides the biggest accuracy boost regardless of model size. Real-world testing during deployment will determine if `base` suffices.

3. **Overlap deduplication edge cases**
   - What we know: Word-level suffix/prefix matching works for simple overlaps
   - What's unclear: How Whisper handles the overlap region -- it may rephrase or re-punctuate the same words differently in each chunk
   - Recommendation: Implement simple word-matching first; add fuzzy matching (Levenshtein or SequenceMatcher ratio) if real-world testing shows false negatives in dedup.

4. **pynput on Windows in dental office environment**
   - What we know: pynput works in whisper-ptt on Deep's home machine
   - What's unclear: Whether pynput global hotkeys work when Dentrix or other dental software has focus
   - Recommendation: Implement with pynput as primary, document that if hotkeys conflict, the web UI buttons are the fallback.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.2.0 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] (create in Wave 0) |
| Quick run command | `pytest tests/ -x --tb=short` |
| Full suite command | `pytest tests/ --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUD-01 | Start/stop session, chunks transcribed and discarded | unit + integration | `pytest tests/test_session_manager.py -x` | Wave 0 |
| TRX-01 | Whisper loads with int8 on CUDA, transcribes audio | unit | `pytest tests/test_whisper_service.py -x` | Wave 0 |
| TRX-02 | Dental vocabulary prompt is included in transcription calls | unit | `pytest tests/test_whisper_service.py::test_dental_prompt -x` | Wave 0 |
| PRV-01 | No network requests during session | unit | `pytest tests/test_session_manager.py::test_no_network -x` | Wave 0 |
| - | VAD correctly detects speech vs silence | unit | `pytest tests/test_vad.py -x` | Wave 0 |
| - | Chunk overlap deduplication | unit | `pytest tests/test_stitcher.py -x` | Wave 0 |
| - | Transcript writer flush-per-chunk | unit | `pytest tests/test_transcript_writer.py -x` | Wave 0 |
| - | SSE endpoint streams transcript updates | integration | `pytest tests/test_routes.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --tb=short`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pyproject.toml` -- new v2 project setup with test configuration
- [ ] `tests/conftest.py` -- shared fixtures: mock audio arrays, fake VAD model, test config
- [ ] `tests/test_session_manager.py` -- covers AUD-01, PRV-01
- [ ] `tests/test_whisper_service.py` -- covers TRX-01, TRX-02
- [ ] `tests/test_vad.py` -- VAD speech detection
- [ ] `tests/test_chunker.py` -- chunk boundary logic
- [ ] `tests/test_stitcher.py` -- overlap deduplication
- [ ] `tests/test_transcript_writer.py` -- file writing, crash safety
- [ ] `tests/test_routes.py` -- SSE endpoint integration
- [ ] Framework install: `pip install pytest pytest-cov pytest-asyncio httpx ruff mypy`

## Sources

### Primary (HIGH confidence)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- model loading, transcribe API, compute types, VRAM benchmarks
- [CTranslate2 quantization docs](https://opennmt.net/CTranslate2/quantization.html) -- GPU compute capability requirements, int8 vs float16 support matrix
- [FastAPI SSE docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/) -- EventSourceResponse, ServerSentEvent API, built-in since 0.135.0
- [HTMX SSE extension](https://htmx.org/extensions/sse/) -- sse-connect, sse-swap attributes, event handling
- [silero-vad GitHub](https://github.com/snakers4/silero-vad) -- 512-sample chunks at 16kHz, v5 API, pysilero-vad 3.3.0
- [whisper-ptt/ptt.py](../../../whisper-ptt/ptt.py) -- proven audio pipeline pattern, sounddevice callback, VAD integration
- [python-sounddevice docs](https://python-sounddevice.readthedocs.io/) -- InputStream API, async integration, v0.5.5

### Secondary (MEDIUM confidence)
- [CTranslate2 GitHub issue #42](https://github.com/SYSTRAN/faster-whisper/issues/42) -- float16 on CC 6.1 GPUs (confirmed not supported, use int8)
- [faster-whisper issue #183](https://github.com/guillaumekln/faster-whisper/issues/183) -- hallucination on silent audio, vad_filter mitigation
- [Whisper model comparison blog](https://whisper-api.com/blog/models/) -- model size vs accuracy benchmarks

### Tertiary (LOW confidence)
- Whisper `small` model VRAM with int8 estimated at ~500MB based on the large-v2 benchmark (11.3GB -> 3.1GB with int8, proportionally scaled to small model's 244M params vs large-v2's 1.5B params). Needs validation on actual GTX 1050 hardware.
- Overlap deduplication with simple word matching -- may need fuzzy matching in practice. Needs real-world testing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified via official docs, proven in whisper-ptt
- Architecture: HIGH -- producer-consumer queue pattern proven in ptt.py, FastAPI SSE verified in official docs
- Pitfalls: HIGH -- GPU compute capability issue verified via CTranslate2 docs and GitHub issues; hallucination issue well-documented
- Discretion recommendations: MEDIUM -- model size and thresholds are educated estimates; real-world dental operatory testing needed

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain -- faster-whisper and CTranslate2 release cycle is quarterly)
