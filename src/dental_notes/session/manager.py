"""Session lifecycle state machine for audio capture and transcription.

Orchestrates AudioCapture, VadDetector, AudioChunker, WhisperService,
stitcher, and TranscriptWriter into a coherent session lifecycle:

    IDLE -> RECORDING -> AUTO_PAUSED -> RECORDING -> STOPPING -> IDLE
                      -> PAUSED -> RECORDING

The processing loop runs in a background daemon thread so Whisper inference
never blocks the asyncio event loop. All state transitions are protected
by a threading.Lock.

AUTO_PAUSED keeps audio capture running and buffers blocks in a rolling
deque. When speech resumes (3+ consecutive speech blocks), the buffer
is replayed into the chunker and recording continues.

Audio data is discarded immediately after transcription -- never stored as
WAV files (AUD-01 compliance).

No network imports or requests are made (PRV-01 compliance).
"""

import collections
import logging
import threading
import time
from enum import Enum
from pathlib import Path

from dental_notes.audio.vad import VadDetector
from dental_notes.config import Settings
from dental_notes.session.speaker import classify_speaker
from dental_notes.session.transcript_writer import TranscriptWriter
from dental_notes.transcription.chunker import AudioChunker
from dental_notes.transcription.stitcher import deduplicate_overlap

logger = logging.getLogger(__name__)

# Audio block size: 100ms at 16kHz = 1600 samples
BLOCK_SIZE = 1600

# Consecutive speech blocks required to confirm resume from auto-pause
SPEECH_CONFIRM_BLOCKS = 3


class SessionState(Enum):
    """Session lifecycle states."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    AUTO_PAUSED = "auto_paused"


class SessionManager:
    """Orchestrates the full capture-to-transcript pipeline.

    Wires together AudioCapture, VadDetector, AudioChunker, WhisperService,
    stitcher, and TranscriptWriter. Manages session lifecycle through the
    state machine.

    WhisperService can be injected via ``_whisper`` for testability, or it
    will be created internally on start().

    For testing, override ``_create_capture`` and ``_create_chunker`` with
    lambdas that return fake objects.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state = SessionState.IDLE
        self._lock = threading.Lock()

        # Pipeline components (initialized on start)
        self._whisper = None  # Can be injected before start()
        self._capture = None
        self._vad = None
        self._chunker = None
        self._writer: TranscriptWriter | None = None

        # Processing thread
        self._processing_thread: threading.Thread | None = None
        self._processing_thread_running = False

        # Accumulated transcript — stored as structured chunks for SSE
        self._chunks: list[tuple[str, str]] = []  # (speaker, text)
        self._prev_tail = ""  # For overlap deduplication
        self._prev_speaker: str | None = None

        # Auto-pause: silence tracking and rolling buffer
        self._silence_duration: float = 0.0
        self._speech_resume_count: int = 0
        self._rolling_buffer: collections.deque = collections.deque()

        # Optional VAD override for testing (set _vad_override before start)
        self._vad_override = None

        # Factory methods (overridable for testing)
        self._create_capture = self._default_create_capture
        self._create_chunker = self._default_create_chunker

    def _default_create_capture(self):
        """Create a real AudioCapture instance."""
        from dental_notes.audio.capture import AudioCapture

        return AudioCapture(self._settings)

    def _default_create_chunker(self, vad: VadDetector) -> AudioChunker:
        """Create a real AudioChunker instance."""
        return AudioChunker(self._settings, vad)

    def start(self, mic_device: int | None = None) -> None:
        """Start a recording session.

        Initializes all pipeline components and launches the background
        processing thread.

        Args:
            mic_device: Optional microphone device index.

        Raises:
            RuntimeError: If not in IDLE state.
        """
        with self._lock:
            if self._state != SessionState.IDLE:
                raise RuntimeError(
                    f"Cannot start: state is {self._state.value}"
                )

            # Initialize audio capture first — fast-fail if no device available
            self._capture = self._create_capture()
            self._capture.start(device_index=mic_device)

            try:
                # Audio works — now load the heavier components
                if self._vad_override is not None:
                    self._vad = self._vad_override
                else:
                    self._vad = VadDetector(
                        threshold=self._settings.vad_threshold
                    )
                self._chunker = self._create_chunker(self._vad)

                if self._whisper is None:
                    from dental_notes.transcription.whisper_service import (
                        WhisperService,
                    )

                    self._whisper = WhisperService(self._settings)
                    self._whisper.load_model()

                self._writer = TranscriptWriter(self._settings.storage_dir)
                self._chunks = []
                self._prev_tail = ""
                self._prev_speaker = None

                # Initialize rolling buffer for auto-pause
                block_size = BLOCK_SIZE
                buffer_maxlen = int(
                    self._settings.rolling_buffer_secs
                    * self._settings.sample_rate
                    / block_size
                )
                self._rolling_buffer = collections.deque(
                    maxlen=max(buffer_maxlen, 1)
                )
                self._silence_duration = 0.0
                self._speech_resume_count = 0
            except Exception:
                # Clean up audio capture if later init fails
                self._capture.stop()
                self._capture = None
                raise

            # Launch processing thread
            self._processing_thread_running = True
            self._processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="session-processing",
            )
            self._processing_thread.start()

            self._state = SessionState.RECORDING
            logger.info("Session started (mic_device=%s)", mic_device)

    def pause(self) -> None:
        """Pause the recording session.

        Stops audio capture but keeps the processing thread alive.
        Works from both RECORDING and AUTO_PAUSED states.

        Raises:
            RuntimeError: If not in RECORDING or AUTO_PAUSED state.
        """
        with self._lock:
            if self._state not in (
                SessionState.RECORDING,
                SessionState.AUTO_PAUSED,
            ):
                raise RuntimeError(
                    f"Cannot pause: state is {self._state.value}"
                )
            self._capture.stop()
            self._state = SessionState.PAUSED
            logger.info("Session paused")

    def resume(self) -> None:
        """Resume the recording session.

        Restarts audio capture.

        Raises:
            RuntimeError: If not in PAUSED state.
        """
        with self._lock:
            if self._state != SessionState.PAUSED:
                raise RuntimeError(
                    f"Cannot resume: state is {self._state.value}"
                )
            self._capture.start()
            self._state = SessionState.RECORDING
            logger.info("Session resumed")

    def stop(self) -> Path:
        """Stop the recording session and finalize the transcript.

        Stops audio capture, flushes remaining chunks, closes the
        transcript writer, and returns the path to the transcript file.

        Returns:
            Path to the completed transcript file.

        Raises:
            RuntimeError: If not in RECORDING or PAUSED state.
        """
        with self._lock:
            if self._state not in (
                SessionState.RECORDING,
                SessionState.PAUSED,
                SessionState.AUTO_PAUSED,
            ):
                raise RuntimeError(
                    f"Cannot stop: state is {self._state.value}"
                )
            self._state = SessionState.STOPPING

        # Stop audio capture
        self._capture.stop()

        # Stop processing thread
        self._processing_thread_running = False
        if self._processing_thread is not None:
            self._processing_thread.join(timeout=5.0)

        # Flush remaining audio in chunker
        remaining = self._chunker.flush()
        if remaining is not None and len(remaining) > 0:
            text = self._whisper.transcribe(remaining)
            if text.strip():
                deduped = deduplicate_overlap(self._prev_tail, text)
                if deduped.strip():
                    speaker = classify_speaker(deduped, self._prev_speaker)
                    self._prev_speaker = speaker
                    separator = "\n\n" if self._chunks else ""
                    self._writer.append(
                        f"{separator}{speaker}: {deduped}"
                    )
                    self._chunks.append((speaker, deduped))

        # Close writer and get path
        self._writer.close()
        transcript_path = self._writer.path

        # Clean up references
        with self._lock:
            self._state = SessionState.IDLE
            self._capture = None
            self._chunker = None
            self._vad = None
            self._writer = None
            self._processing_thread = None

        logger.info("Session stopped. Transcript: %s", transcript_path)
        return transcript_path

    def _processing_loop(self) -> None:
        """Background thread: read audio -> chunk -> transcribe -> write.

        Runs until _processing_thread_running is set to False.
        Audio data (numpy arrays) go out of scope after transcription
        and are garbage collected -- never stored (AUD-01).

        Handles RECORDING state (normal pipeline) and AUTO_PAUSED state
        (rolling buffer with speech detection for resume).
        """
        while self._processing_thread_running:
            # If paused, sleep briefly and continue
            if self._state == SessionState.PAUSED:
                time.sleep(0.05)
                continue

            # Get audio block from capture queue
            block = self._capture.get_block()
            if block is None:
                time.sleep(0.01)
                continue

            # Handle AUTO_PAUSED state: buffer audio and watch for speech
            if self._state == SessionState.AUTO_PAUSED:
                self._process_auto_paused(block)
                continue

            # --- RECORDING state: normal pipeline ---

            # Check VAD for silence tracking (auto-pause detection)
            is_speech = self._vad.is_speech(block)
            if is_speech:
                self._silence_duration = 0.0
            else:
                block_duration = len(block) / self._settings.sample_rate
                self._silence_duration += block_duration

                # Check for auto-pause trigger
                if (
                    self._settings.auto_pause_enabled
                    and self._silence_duration
                    >= self._settings.auto_pause_silence_secs
                ):
                    with self._lock:
                        if self._state == SessionState.RECORDING:
                            # Clear rolling buffer at START of auto-pause
                            # (prevents replay of pre-pause audio)
                            self._rolling_buffer.clear()
                            self._speech_resume_count = 0
                            self._state = SessionState.AUTO_PAUSED
                            logger.info(
                                "Auto-pause: %0.1fs of silence detected",
                                self._silence_duration,
                            )
                    continue

            # Feed block to chunker
            chunk = self._chunker.feed(block)
            # block goes out of scope here -- DISCARDED

            if chunk is not None:
                # Transcribe the chunk
                text = self._whisper.transcribe(chunk)
                # chunk goes out of scope after this line -- DISCARDED

                if text.strip():
                    # Deduplicate overlap with previous transcript
                    deduped = deduplicate_overlap(self._prev_tail, text)
                    if deduped.strip():
                        speaker = classify_speaker(deduped, self._prev_speaker)
                        self._prev_speaker = speaker
                        separator = "\n\n" if self._chunks else ""
                        self._writer.append(
                            f"{separator}{speaker}: {deduped}"
                        )
                        self._chunks.append((speaker, deduped))
                        # Keep tail for next deduplication
                        self._prev_tail = text

    def _process_auto_paused(self, block) -> None:
        """Handle a block during AUTO_PAUSED state.

        Appends block to rolling buffer and checks for speech to resume.
        """
        self._rolling_buffer.append(block)
        is_speech = self._vad.is_speech(block)

        if is_speech:
            self._speech_resume_count += 1
            if self._speech_resume_count >= SPEECH_CONFIRM_BLOCKS:
                self._resume_from_auto_pause()
        else:
            self._speech_resume_count = 0

    def _resume_from_auto_pause(self) -> None:
        """Resume recording from AUTO_PAUSED state.

        Replays rolling buffer contents into the chunker, then transitions
        back to RECORDING state.
        """
        with self._lock:
            # Replay buffered audio into chunker
            for buffered_block in self._rolling_buffer:
                self._chunker.feed(buffered_block)
            self._rolling_buffer.clear()
            self._state = SessionState.RECORDING
            self._silence_duration = 0.0
            self._speech_resume_count = 0
            logger.info(
                "Auto-pause ended: speech detected, resuming recording"
            )

    def get_transcript(self) -> str:
        """Return the accumulated transcript as plain text."""
        return "\n\n".join(f"{s}: {t}" for s, t in self._chunks)

    def get_chunk_count(self) -> int:
        """Return the number of transcript chunks so far."""
        return len(self._chunks)

    def get_chunks(self, start: int = 0) -> list[tuple[str, str]]:
        """Return transcript chunks from the given index onward."""
        return self._chunks[start:]

    def get_state(self) -> SessionState:
        """Return the current session state."""
        return self._state

    def is_active(self) -> bool:
        """Return True if the session is RECORDING, PAUSED, or AUTO_PAUSED."""
        return self._state in (
            SessionState.RECORDING,
            SessionState.PAUSED,
            SessionState.AUTO_PAUSED,
        )

    def get_level(self) -> float:
        """Return current audio level (delegates to AudioCapture).

        Returns 0.0 if no capture is active.
        """
        if self._capture is None:
            return 0.0
        return self._capture.get_level()
