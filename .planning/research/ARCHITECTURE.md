# Architecture Research

**Domain:** Local-first ambient clinical note-taking for dental practices
**Researched:** 2026-03-05
**Confidence:** HIGH

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                         │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │  Recording     │  │  Transcript   │  │  SOAP Note Editor +     │  │
│  │  Controls      │  │  Review Panel │  │  Copy-to-Dentrix        │  │
│  └───────┬───────┘  └───────┬───────┘  └────────────┬─────────────┘  │
│          │                  │                        │                │
├──────────┴──────────────────┴────────────────────────┴────────────────┤
│                       Local HTTP API (FastAPI)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ /record  │  │ /transcr │  │ /extract │  │ /sessions            │  │
│  │ start/   │  │ ibe      │  │          │  │ (CRUD + finalize)    │  │
│  │ stop     │  │          │  │          │  │                      │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       │              │             │                   │              │
├───────┴──────────────┴─────────────┴───────────────────┴──────────────┤
│                       Processing Pipeline                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐    │
│  │ Audio        │  │ Transcription│  │ Clinical Extraction      │    │
│  │ Capture      │  │ Engine       │  │ (Local LLM via Ollama)   │    │
│  │ (sounddevice)│  │ (faster-     │  │                          │    │
│  │              │  │  whisper)    │  │                          │    │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘    │
│         │                 │                        │                  │
├─────────┴─────────────────┴────────────────────────┴──────────────────┤
│                       Storage Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐    │
│  │ Temp Audio   │  │ Session DB   │  │ Config                   │    │
│  │ (WAV files   │  │ (SQLite)     │  │ (JSON)                   │    │
│  │  auto-purge) │  │              │  │                          │    │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Audio Capture | Continuous mic recording during appointment, streaming chunks to disk | `sounddevice.InputStream` callback writing 16kHz mono WAV chunks to temp directory |
| Transcription Engine | Convert WAV audio to timestamped text with speaker labels | `faster-whisper` (medium/large-v3 model) + `whisperX` for word alignment + `pyannote-audio` for speaker diarization |
| Clinical Extractor | Filter clinical content from chitchat, structure into SOAP note + CDT codes | Local LLM via Ollama (Llama 3.1 8B or Qwen3 8B at Q4_K_M quantization) with structured JSON output |
| Session Manager | Track appointment lifecycle: recording -> transcribed -> drafted -> finalized -> purged | SQLite database + filesystem for temp audio |
| Review UI | Display transcript alongside draft SOAP note, allow edits, copy to clipboard | FastAPI serving HTML/JS via browser (localhost), HTMX for reactivity |
| Config Manager | Microphone selection, model settings, note templates, consent preferences | JSON file on disk, API endpoints for read/write |

## Recommended Project Structure

```
dental-ambient/
├── src/
│   └── dental_ambient/
│       ├── __init__.py
│       ├── main.py              # FastAPI app entry point
│       ├── config.py            # Settings management (JSON-backed)
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── capture.py       # sounddevice recording, WAV writing
│       │   ├── devices.py       # Mic enumeration and selection
│       │   └── vad.py           # Voice activity detection (silero-vad)
│       ├── transcription/
│       │   ├── __init__.py
│       │   ├── engine.py        # faster-whisper transcription
│       │   ├── diarization.py   # pyannote speaker diarization
│       │   └── alignment.py     # WhisperX word-level alignment
│       ├── extraction/
│       │   ├── __init__.py
│       │   ├── llm.py           # Ollama client, structured output
│       │   ├── prompts.py       # Clinical extraction prompt templates
│       │   └── cdt_codes.py     # CDT code lookup and suggestion
│       ├── sessions/
│       │   ├── __init__.py
│       │   ├── models.py        # Session, Transcript, SOAPNote dataclasses
│       │   ├── storage.py       # SQLite session persistence
│       │   └── cleanup.py       # Ephemeral data purge after finalization
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── recording.py     # POST /api/record/start, /api/record/stop
│       │   ├── transcription.py # POST /api/transcribe/{session_id}
│       │   ├── extraction.py    # POST /api/extract/{session_id}
│       │   ├── sessions.py      # GET/PUT/DELETE session management
│       │   └── config.py        # GET/PUT settings
│       └── ui/
│           ├── __init__.py
│           └── routes.py        # Serves HTML templates
├── static/
│   ├── css/
│   │   └── app.css              # Minimal, functional CSS
│   └── js/
│       └── app.js               # HTMX + recording controls + clipboard
├── templates/
│   ├── base.html                # Layout shell
│   ├── dashboard.html           # Session list / home
│   ├── recording.html           # Active recording view
│   ├── review.html              # Side-by-side transcript + SOAP note
│   └── settings.html            # Configuration page
├── tests/
│   ├── test_audio_capture.py
│   ├── test_transcription.py
│   ├── test_extraction.py
│   ├── test_sessions.py
│   └── fixtures/
│       ├── sample_audio.wav     # Short test recording
│       └── sample_transcript.json
├── pyproject.toml
├── README.md
└── .env.example                 # HF_TOKEN (for pyannote download)
```

### Structure Rationale

- **`audio/`:** Isolated from transcription because recording and transcription happen at different times and can be tested independently. The capture module is the only component that touches hardware (microphone).
- **`transcription/`:** Separate from extraction because transcription is compute-heavy GPU work (Whisper + diarization) that runs as a batch job, while extraction is a separate LLM call.
- **`extraction/`:** Contains all LLM interaction and clinical logic. Changes to prompt engineering or LLM model don't affect the rest of the system.
- **`sessions/`:** The glue that tracks an appointment through its lifecycle. Every other component reads/writes session state through this module.
- **`routes/`:** Thin HTTP handlers. Business logic lives in the domain modules, not here.
- **`ui/`:** Server-rendered HTML with HTMX. No build step, no JavaScript framework, no complexity.

## Architectural Patterns

### Pattern 1: Batch Processing Pipeline (not real-time streaming)

**What:** Record the full appointment audio to disk, then transcribe and extract as sequential batch steps after recording stops. Do NOT attempt real-time streaming transcription.

**When to use:** Always, for this system.

**Trade-offs:**
- PRO: Dramatically simpler architecture (no WebSocket streaming, no chunked transcription stitching, no partial result management)
- PRO: Better accuracy -- Whisper works best on complete utterances, not 2-second chunks
- PRO: The dentist reviews the note AFTER the appointment anyway, so real-time adds zero value
- PRO: GPU is either doing transcription OR LLM extraction, never contending
- CON: 30-60 second wait after recording stops before seeing transcript (acceptable given the workflow)

**Rationale:** Real-time transcription would mean chunking audio into ~5-second windows, transcribing each, stitching results, and displaying partial text -- all while the dentist is focused on the patient and not looking at a screen. The review happens after the appointment. Batch processing is the clear correct choice. The existing `whisper-ptt` system proves that faster-whisper on a GTX 1070 Ti transcribes a few minutes of audio in seconds.

### Pattern 2: Session State Machine

**What:** Each appointment follows a strict state progression with automated cleanup.

**States:**
```
IDLE → RECORDING → RECORDED → TRANSCRIBING → TRANSCRIBED
    → EXTRACTING → DRAFTED → FINALIZED → PURGED
```

**When to use:** Every appointment session.

**Trade-offs:**
- PRO: Clear lifecycle prevents data from lingering (HIPAA compliance)
- PRO: Each state transition is a testable unit
- PRO: UI can show exactly what's happening and what's possible
- CON: Slightly more upfront design work

**Example:**
```python
class SessionState(str, Enum):
    RECORDING = "recording"
    RECORDED = "recorded"         # Audio on disk, ready to process
    TRANSCRIBING = "transcribing" # Whisper running
    TRANSCRIBED = "transcribed"   # Full transcript available
    EXTRACTING = "extracting"     # LLM structuring note
    DRAFTED = "drafted"           # SOAP note ready for review
    FINALIZED = "finalized"       # Dentist approved, ready to copy
    PURGED = "purged"             # Audio + transcript deleted

VALID_TRANSITIONS = {
    SessionState.RECORDING: [SessionState.RECORDED],
    SessionState.RECORDED: [SessionState.TRANSCRIBING],
    SessionState.TRANSCRIBING: [SessionState.TRANSCRIBED],
    SessionState.TRANSCRIBED: [SessionState.EXTRACTING],
    SessionState.EXTRACTING: [SessionState.DRAFTED],
    SessionState.DRAFTED: [SessionState.FINALIZED, SessionState.EXTRACTING],  # re-extract
    SessionState.FINALIZED: [SessionState.PURGED],
}
```

### Pattern 3: GPU Time-Sharing (Sequential, Not Concurrent)

**What:** Whisper and the local LLM share the same GPU but never run simultaneously. Load one model, run it, unload, load the next.

**When to use:** On hardware with 8GB VRAM (GTX 1070 Ti), which cannot hold both models simultaneously.

**Trade-offs:**
- PRO: Works on 8GB VRAM GPUs without OOM errors
- PRO: Simple -- no GPU memory management complexity
- CON: Model loading adds ~5-10 seconds per transition
- Mitigation: Keep Whisper loaded by default (most frequent use). Load LLM only when extraction is triggered. Consider `ollama keep_alive` settings.

**Implementation note:** faster-whisper medium model uses ~2.5GB VRAM. A 7B LLM at Q4_K_M uses ~4.5GB VRAM. These cannot coexist on an 8GB card. The pipeline must be: record -> unload nothing (Whisper stays loaded) -> transcribe -> unload Whisper -> load LLM -> extract -> unload LLM -> load Whisper for next session.

On machines with 12GB+ VRAM (RTX cards), both models could potentially stay loaded, but designing for the minimum hardware (GTX 1050/1070) is correct.

## Data Flow

### Primary Pipeline Flow

```
[Dentist starts appointment]
    │
    ▼
[Click "Start Recording" in browser]
    │
    ▼
[Audio Capture] ─── sounddevice callback ──→ [WAV file on disk]
    │                (16kHz mono, streaming     (temp directory,
    │                 write via soundfile)        grows during appt)
    │
[Click "Stop Recording"]
    │
    ▼
[Session state: RECORDED]
    │
    ▼
[Click "Transcribe" or auto-trigger]
    │
    ▼
[Transcription Engine]
    │
    ├── faster-whisper loads WAV ──→ raw transcript segments
    │
    ├── whisperX alignment ──→ word-level timestamps
    │
    ├── pyannote diarization ──→ speaker labels (Speaker 1, Speaker 2...)
    │
    └── merge ──→ timestamped, speaker-labeled transcript
    │
    ▼
[Session state: TRANSCRIBED]
    │
    ▼
[Clinical Extraction]
    │
    ├── Transcript → Ollama (structured JSON output)
    │     Prompt: "Given this dental appointment transcript,
    │              extract clinical content into SOAP format
    │              with CDT codes. Ignore chitchat."
    │
    └── Structured output → SOAP note + CDT codes
    │
    ▼
[Session state: DRAFTED]
    │
    ▼
[Review UI: side-by-side view]
    │
    ├── Left panel: full transcript (speaker-labeled, timestamped)
    │
    ├── Right panel: editable SOAP note draft
    │
    └── Actions: [Edit] [Re-extract] [Copy to Clipboard] [Finalize]
    │
    ▼
[Click "Finalize"]
    │
    ├── SOAP note text saved to session record
    ├── Audio WAV file deleted from disk
    ├── Raw transcript marked for deletion
    └── Session state: FINALIZED → PURGED
```

### Audio Capture Detail

```
[Microphone] → [sounddevice.InputStream callback]
                    │
                    ├── Writes audio chunks to thread-safe queue
                    │
                    └── Writer thread drains queue → appends to WAV file
                        (soundfile.SoundFile in write mode)

WAV file format: 16kHz, mono, 16-bit PCM
Typical size: ~15MB per 10-minute appointment
Storage: temp directory, auto-cleaned on finalization
```

### Key Data Flows

1. **Audio to disk:** The sounddevice callback runs in a high-priority audio thread. It must ONLY append to a queue (never do I/O). A separate writer thread drains the queue and writes to disk. This is the proven pattern from whisper-ptt.

2. **Transcript to extraction:** The full transcript (with speaker labels and timestamps) is passed to the LLM as a single prompt. This is NOT a streaming/incremental process -- the LLM gets the complete conversation context.

3. **Session lifecycle:** All state transitions go through the session manager, which enforces valid transitions and triggers cleanup. The UI polls or uses SSE to show current state.

## Component Communication

### Process Architecture

Everything runs in a **single Python process** with a FastAPI server. There are no separate services to start, no Docker containers, no message queues.

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Browser <-> FastAPI | HTTP (REST) + SSE for status updates | HTMX handles partial page updates via HTTP |
| FastAPI <-> Audio Capture | In-process function calls | Audio capture runs on a background thread within the same process |
| FastAPI <-> Transcription | In-process, sequential | Transcription blocks the endpoint (async with background task) |
| FastAPI <-> Ollama | HTTP (localhost:11434) | Ollama runs as a separate system service. FastAPI calls its REST API |
| FastAPI <-> SQLite | In-process via `aiosqlite` or `sqlite3` | Direct file access, no separate DB server |
| FastAPI <-> Filesystem | Direct file I/O | WAV files in temp dir, config in project dir |

**Why single process:** This is a single-user desktop tool, not a multi-tenant web service. A single FastAPI process handles everything. The only external dependency is Ollama (which runs as a system service independently). This eliminates IPC complexity, deployment complexity, and failure modes.

**Why Ollama as separate service (not in-process LLM):** Ollama manages GPU memory, model loading/unloading, and quantization. Reimplementing this in-process would be a massive amount of work for zero benefit. Ollama also allows easy model swapping and updates without touching the application code.

### Inter-Component Contracts

```
Audio Capture → produces → WAV file path (str)
Transcription → consumes WAV path → produces → TranscriptResult
    TranscriptResult:
        segments: list[Segment]  # text, start, end, speaker
        full_text: str           # concatenated, speaker-labeled
        duration_seconds: float

Clinical Extraction → consumes TranscriptResult → produces → ClinicalNote
    ClinicalNote:
        title: str               # ALL CAPS procedure summary
        chief_complaint: str
        clinical_findings: str
        treatment_plan: str
        procedure_details: str | None
        follow_up: str
        cdt_codes: list[CDTCode]
        raw_json: dict           # Original LLM output for debugging
```

## Real-Time vs Batch: Decision

**Decision: Batch processing.** Record the full appointment, then transcribe and extract after.

| Factor | Real-Time | Batch | Winner |
|--------|-----------|-------|--------|
| Accuracy | Lower (small audio chunks, no future context) | Higher (full conversation context) | Batch |
| Complexity | High (WebSocket streaming, chunk stitching, partial results) | Low (file in, text out) | Batch |
| User workflow | Dentist is with patient, not watching screen | Dentist reviews after patient leaves | Batch |
| GPU contention | Continuous GPU use during appointment | GPU used only during processing phase | Batch |
| Diarization | Very difficult on small chunks | Works well on complete audio | Batch |
| Latency | Instant (but low quality) | 30-90 seconds after stop (acceptable) | Tie |

Processing time estimates for a 15-minute appointment on GTX 1070 Ti:
- Transcription (faster-whisper medium): ~30-60 seconds
- Diarization (pyannote 3.1): ~20-40 seconds
- LLM extraction (Llama 3.1 8B via Ollama): ~15-30 seconds
- **Total: ~1-2 minutes** (well within acceptable range since dentist transitions between patients)

## Speaker Diarization Architecture

### Pipeline

```
[WAV file] → [faster-whisper] → raw segments with timestamps
                                      │
                                      ▼
[WAV file] → [pyannote-audio 3.1] → speaker segments with timestamps
                                      │
                                      ▼
                              [whisperX alignment] → word-level timestamps
                                      │
                                      ▼
                              [merge] → each word/segment tagged with speaker
```

### Speaker Identification Strategy

In a dental appointment, there are typically 2-3 speakers:
- **Dentist** (most clinical content)
- **Patient** (chief complaint, history, responses)
- **Assistant** (procedural coordination, materials)

Pyannote will label them as "SPEAKER_00", "SPEAKER_01", etc. The system should:

1. **Default assumption:** The speaker who talks most about clinical findings/treatment is the dentist
2. **First-session calibration:** After the first appointment, let the dentist tag which speaker label is them. The system remembers speaker embedding similarity for future sessions.
3. **MVP approach:** Label speakers generically. The dentist can mentally map speakers during review. Automatic speaker identification is a Phase 2+ feature.

### Pyannote Setup Requirements

- Requires a free HuggingFace account and token (one-time setup)
- Models downloaded once (~300MB), then run fully offline
- Runs on GPU (CUDA) for speed; CPU fallback possible but slow
- Speaker diarization 3.1 model achieves DER of ~11-19% on standard benchmarks

## Ephemeral Storage and Cleanup

### Storage Layout

```
~/.dental-ambient/                 # App data directory
├── config.json                    # User settings (persists)
├── dental-ambient.db              # SQLite session database (persists)
└── temp/                          # Ephemeral appointment data
    ├── session-{uuid}/
    │   ├── recording.wav          # Raw audio (deleted on finalize)
    │   ├── transcript.json        # Full transcript (deleted on finalize)
    │   └── draft.json             # SOAP note draft (deleted on finalize)
    └── ...
```

### Cleanup Rules

| Event | Action |
|-------|--------|
| Session finalized | Delete WAV, transcript JSON, draft JSON. Keep only final SOAP note text in DB. |
| Session abandoned (>24 hours in RECORDED/TRANSCRIBED state) | Delete all temp files. Mark session as abandoned. |
| App startup | Scan temp dir for orphaned sessions. Prompt user to finalize or delete. |
| WAV file | Never persists longer than needed. Deleted as soon as note is finalized. |

### HIPAA Alignment

- Audio files are the most sensitive data and are deleted first
- Transcripts contain PHI and are deleted on finalization
- Only the finalized SOAP note text remains (and even that is ephemeral -- it's pasted into Dentrix, which is the system of record)
- No data ever leaves the local machine
- SQLite DB could optionally be encrypted (SQLCipher) but is low priority since it only stores finalized note text temporarily

## UI Architecture: FastAPI + HTMX (Browser-Based)

### Why browser-based, not native

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **FastAPI + HTMX (localhost)** | No build step, no framework, Python-only stack, works on any machine with a browser | Requires browser open, slightly less "native" feel | **Use this** |
| Electron | Desktop app feel | 200MB+ installer, Chromium bundled, Node.js dependency, over-engineered for this | No |
| Tauri | Small installer, native feel | Rust build toolchain, complexity for a single-user tool | No |
| Native Windows (tkinter/PyQt) | No browser needed | Ugly UIs, painful layout, hard to iterate on | No |

**The user opens `http://localhost:8910` in their browser.** That is the entire "install" from the UI perspective. The FastAPI server is the app.

### HTMX Integration Pattern

HTMX eliminates the need for a JavaScript framework while providing dynamic page updates. The server renders HTML fragments, and HTMX swaps them into the page.

```html
<!-- Recording control -->
<button hx-post="/api/record/start"
        hx-target="#recording-status"
        hx-swap="innerHTML">
    Start Recording
</button>

<!-- Status polling during transcription -->
<div id="session-status"
     hx-get="/api/sessions/{id}/status"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
    Processing...
</div>
```

### UI Screens

1. **Dashboard:** List of today's sessions. Start new recording. Quick access to recent drafts.
2. **Recording:** Large red recording indicator. Timer. Stop button. Mic level visualization (optional).
3. **Processing:** Progress indicator showing current step (transcribing... extracting...).
4. **Review:** Side-by-side layout. Left = scrollable transcript (speaker-labeled). Right = editable SOAP note. Copy button. Finalize button.
5. **Settings:** Mic selection dropdown. Model preferences. Note template customization.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 dentist, 5-10 patients/day | Current design. Single process, single GPU, no DB optimization needed. |
| 2-3 dentists, same office | Multiple instances on different machines. Each machine runs its own instance. No shared state needed. |
| Multi-office | Each office has its own machine. No central server. Deploy via installer or script. |

### Scaling Priorities

1. **First bottleneck -- GPU processing time:** If a 30-minute appointment takes 3+ minutes to process, upgrade the Whisper model size (use `medium` instead of `large-v3`) or upgrade GPU. On GTX 1070 Ti, `medium` is the sweet spot.
2. **Second bottleneck -- LLM quality:** If Llama 3.1 8B produces poor clinical notes, the fix is better prompts first, then consider a larger model (requires better GPU) or switching to a specialized medical model.

## Anti-Patterns

### Anti-Pattern 1: Real-Time Streaming Transcription

**What people do:** Stream audio chunks via WebSocket to Whisper for live transcription during the appointment.
**Why it's wrong:** Adds enormous complexity (chunk management, stitching, partial results, WebSocket reliability) for zero user value -- the dentist is focused on the patient during the appointment and reviews the note afterward. Accuracy suffers because Whisper works best with full context, not 5-second chunks.
**Do this instead:** Batch transcribe the complete recording after the appointment ends.

### Anti-Pattern 2: In-Process LLM Loading

**What people do:** Load the LLM (via llama-cpp-python or ctransformers) directly in the FastAPI process to avoid the Ollama dependency.
**Why it's wrong:** You'd have to manage GPU memory allocation, model quantization, context windows, and structured output formatting yourself. Ollama does all of this. You'd also lose the ability to easily swap models via a simple `ollama pull` command.
**Do this instead:** Use Ollama as a local service. It's already designed for exactly this use case.

### Anti-Pattern 3: Storing Audio Long-Term

**What people do:** Keep audio recordings "for reference" or "in case the note needs to be regenerated."
**Why it's wrong:** Audio is the most PHI-rich data in the system. Storing it creates liability, increases storage requirements, and violates the principle of data minimization. If the note needs to be regenerated, the dentist can re-record.
**Do this instead:** Delete audio immediately upon finalization. The SOAP note is the deliverable.

### Anti-Pattern 4: Complex JavaScript Frontend

**What people do:** Build a React/Vue/Angular SPA with WebSocket connections, client-side state management, and a build pipeline.
**Why it's wrong:** This is a single-user tool opened on localhost. There is no concurrent user problem, no SEO requirement, no offline-first requirement. A JS framework adds build complexity, dependency management, and debugging difficulty for a tool that needs to "just work."
**Do this instead:** Server-rendered HTML with HTMX for dynamic updates. Zero build step. Inspect the HTML in browser DevTools to debug.

### Anti-Pattern 5: Premature Speaker Identification

**What people do:** Build a complex speaker identification system before the basic pipeline works.
**Why it's wrong:** Speaker diarization (labeling segments as SPEAKER_00, SPEAKER_01) is already provided by pyannote. Identifying which speaker is the dentist vs. patient requires voice enrollment, embedding comparison, and calibration -- all of which are secondary to getting accurate transcripts and good clinical notes.
**Do this instead:** Ship with anonymous speaker labels first. Add dentist identification as a later enhancement once the core pipeline is proven.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Ollama (localhost:11434) | HTTP REST API | Must be installed and running. App should check on startup and show clear error if not found. Model must be pre-pulled (`ollama pull llama3.1:8b-instruct-q4_K_M`). |
| HuggingFace (one-time) | Token for pyannote model download | Needed only once during setup. Models cached locally after first download. No runtime internet dependency. |
| Dentrix | Copy-paste (clipboard) | No API integration. The user copies text from the browser and pastes into Dentrix. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Audio capture <-> Session manager | Function call: `start_recording(session_id)` returns `Path` | Audio module is stateless -- it writes to a path and returns. Session manager owns the path. |
| Transcription <-> Session manager | Function call: `transcribe(wav_path)` returns `TranscriptResult` | Transcription is a pure function: WAV in, transcript out. No side effects. |
| Extraction <-> Ollama | HTTP POST to `http://localhost:11434/api/chat` with JSON schema | Uses Ollama's structured output feature. Pydantic model defines the response schema. |
| Session manager <-> SQLite | `aiosqlite` or `sqlite3` via repository pattern | Thin data layer. No ORM needed for this scale. |
| UI <-> FastAPI | HTMX attributes trigger HTTP requests, server returns HTML fragments | No WebSocket needed. SSE or polling for status updates during processing. |

## Suggested Build Order

Build and test components independently, bottom-up:

### Phase 1: Audio Capture (standalone, testable without GPU)
- `sounddevice` recording to WAV file
- Start/stop controls via CLI first, then HTTP endpoint
- Mic enumeration and selection
- **Test:** Record 30 seconds, verify WAV file is valid and playable
- **Dependencies:** None

### Phase 2: Transcription Engine (requires GPU + test audio files)
- `faster-whisper` loading and transcription
- Test with pre-recorded WAV files (no audio capture needed)
- **Test:** Feed a test WAV, get accurate transcript text
- **Dependencies:** None (uses pre-recorded files)

### Phase 3: Session Management + Storage (no GPU needed)
- SQLite schema, session CRUD
- State machine with transition validation
- Temp file management and cleanup
- **Test:** Create session, advance through states, verify cleanup
- **Dependencies:** None

### Phase 4: Clinical Extraction (requires Ollama + test transcripts)
- Ollama client with structured JSON output
- Dental SOAP note prompt engineering
- CDT code extraction
- **Test:** Feed a sample transcript, get structured SOAP note
- **Dependencies:** Ollama installed and running

### Phase 5: Basic UI + End-to-End Pipeline
- FastAPI routes connecting all components
- HTMX-based recording, processing, and review pages
- Copy-to-clipboard functionality
- **Test:** Full appointment simulation: record -> transcribe -> extract -> review -> copy -> finalize
- **Dependencies:** Phases 1-4

### Phase 6: Speaker Diarization (enhancement)
- pyannote-audio integration
- Speaker-labeled transcript display
- **Test:** Multi-speaker recording produces labeled transcript
- **Dependencies:** Phase 2 (transcription engine)

### Phase 7: Polish and Hardening
- Error handling for all failure modes (GPU OOM, Ollama not running, mic unavailable)
- Startup health checks
- Auto-cleanup of abandoned sessions
- Note template customization
- **Dependencies:** Phase 5

**Key insight:** Phases 1, 2, 3, and 4 can be developed and tested independently. Phase 5 integrates them. Phase 6 is additive (diarization can be layered onto the existing transcription pipeline without restructuring).

## Sources

- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- CTranslate2-based Whisper, proven in whisper-ptt
- [WhisperX GitHub](https://github.com/m-bain/whisperX) -- Word-level alignment + diarization pipeline
- [pyannote speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) -- Speaker diarization model, DER ~11-19%
- [Ollama Structured Outputs](https://ollama.com/blog/structured-outputs) -- JSON schema-based output for clinical extraction
- [Ollama GPU Calculator](https://aleibovici.github.io/ollama-gpu-calculator/) -- VRAM requirements for model sizing
- [Ollama Performance Tuning](https://dasroot.net/posts/2026/01/ollama-performance-tuning-gpu-acceleration-model-quantization/) -- Q4_K_M quantization, context window management
- [GTX 1070 Ti for LLMs](https://www.techreviewer.com/tech-specs/nvidia-gtx-1070-ti-gpu-for-llms/) -- 8GB VRAM limitations and model sizing
- [python-sounddevice](https://python-sounddevice.readthedocs.io/) -- Audio capture library, callback-based streaming
- [Best Speaker Diarization Models 2026](https://brasstranscripts.com/blog/speaker-diarization-models-comparison) -- Pyannote 3.1 recommended
- whisper-ptt (`~/claude/whisper-ptt/ptt.py`) -- Proven local Whisper + sounddevice pattern on Deep's hardware

---
*Architecture research for: local-first ambient clinical note-taking (dental)*
*Researched: 2026-03-05*
