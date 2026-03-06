# Phase 1: Streaming Capture and Transcription - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Continuously capture audio from a microphone in small chunks, transcribe each chunk locally via faster-whisper, discard the audio, and accumulate a growing plain-text transcript. The dentist can start, pause, resume, and stop a session from the browser or via keyboard shortcut. A basic volume indicator confirms the mic is active. All processing stays on the local GPU with no network requests. This phase delivers a working capture-to-transcript pipeline — clinical extraction and full review UI come in later phases.

</domain>

<decisions>
## Implementation Decisions

### Chunk size and boundaries
- Hybrid chunking: VAD-driven silence detection to find natural speech boundaries, with a maximum duration cap to force a cut during continuous speech
- Skip chunks where VAD detects no speech — do not send noise-only audio to Whisper (prevents hallucinations on dental equipment noise like suction, handpieces, ultrasonic scalers)
- Overlap chunks by ~1 second at boundaries to prevent word splitting across chunk edges
- Auto-deduplicate repeated words in the overlap region when stitching chunk transcripts together
- Show a basic audio level indicator in the UI so the dentist can confirm the mic is picking up speech

### Session start/stop flow
- Start and stop via both a browser button (FastAPI + HTMX web UI) and a keyboard shortcut
- Pause and resume supported within a single session (e.g. dentist steps out, takes a phone call)
- Transcript saved to a text file automatically when the session is stopped
- No live transcript display during the procedure (out of scope per requirements) — the dentist sees text accumulating as confirmation it's working

### Dental vocabulary prompt
- Universal tooth numbering system (1-32) — US standard
- Full-service practice vocabulary covering: restorative (composites, amalgam, crowns, bridges, onlays, inlays, e.max, zirconia, PFM), perio (prophy, SRP, pocket depths, BOP), endo (pulpectomy, access, working length, obturation), oral surgery (simple/surgical extractions, bone grafting, sutures, socket preservation), implants and implant crowns, prosthetics (dentures, partials), orthodontics (Invisalign), cosmetics (veneers, bonding, bleaching), sleep apnea devices
- Specific brand names for Whisper initial_prompt: Shofu, Ivoclar, Filtek, RelyX, Gluma
- Mix of full surface names (mesial, occlusal, distal, buccal, lingual) and abbreviations (MOD, DO, BL) — prompt should include both forms
- CDT code format awareness (D####) for when the dentist verbally references procedure codes

### Transcript accumulation
- Plain text (.txt) format — no JSON, no structured metadata
- No timestamps under normal operation (not needed for clinical workflow)
- User-configurable storage folder (setting in the web UI or config file)
- Append each chunk's transcript to the file for crash safety

### Claude's Discretion
- Maximum chunk duration before forced cut (balance VRAM usage on GTX 1050 vs. Whisper accuracy with longer context)
- Silence gap threshold for VAD-driven chunk boundaries (tune for dental conversation cadence)
- Crash recovery strategy (flush-per-chunk vs. periodic flush — leaning flush-per-chunk for reliability)
- Transcript file naming convention (date-time based, no patient info, privacy-safe)
- Whisper model size selection within GTX 1050 4GB VRAM constraint
- Keyboard shortcut key choice for start/stop/pause

</decisions>

<specifics>
## Specific Ideas

- whisper-ptt already proves the sounddevice → audio queue → faster-whisper pipeline on Deep's hardware; reuse that pattern
- The Whisper initial_prompt pattern from ptt.py (vocabulary hints) directly applies — expand it with dental terminology
- silero-vad integration from ptt.py can be reused for speech detection and noise-only chunk skipping
- User mentioned wanting it to work "across many devices" with minimal resources — GTX 1050 (4GB) is the hard floor

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `whisper-ptt/ptt.py`: sounddevice callback with audio queue (line 498), VAD monitor thread, WhisperModel loading (line 222), INITIAL_PROMPT pattern for vocabulary hints
- `backend/prompts/soap_note.py`: SOAP note system prompt with CDT codes and JSON schema — reusable in Phase 2

### Established Patterns
- Audio capture: `sd.InputStream(samplerate=16000, channels=1, callback=audio_callback, blocksize=1600)` with `queue.Queue(maxsize=200)`
- Whisper loading: `WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")` — lazy-loaded on first use
- VAD: silero-vad with 512-sample chunks at 16kHz, configurable threshold

### Integration Points
- New v2 code starts fresh — no integration with legacy Flutter/FastAPI backend
- FastAPI server will host both the API endpoints (start/stop/pause/status) and the HTMX web UI
- Keyboard shortcut listener will run alongside the FastAPI server process

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-streaming-capture-and-transcription*
*Context gathered: 2026-03-06*
