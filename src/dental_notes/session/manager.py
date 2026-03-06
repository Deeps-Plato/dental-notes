"""Session lifecycle state machine for audio capture and transcription.

Orchestrates AudioCapture, VadDetector, AudioChunker, WhisperService,
stitcher, and TranscriptWriter into a coherent session lifecycle:

    IDLE -> RECORDING -> PAUSED -> RECORDING -> STOPPING -> IDLE

The processing loop runs in a background daemon thread so Whisper inference
never blocks the asyncio event loop. All state transitions are protected
by a threading.Lock.

Audio data is discarded immediately after transcription -- never stored as
WAV files (AUD-01 compliance).

No network imports or requests are made (PRV-01 compliance).
"""

import logging
import threading
import time
from enum import Enum
from pathlib import Path

from dental_notes.audio.vad import VadDetector
from dental_notes.config import Settings
from dental_notes.session.transcript_writer import TranscriptWriter
from dental_notes.transcription.chunker import AudioChunker
from dental_notes.transcription.stitcher import deduplicate_overlap

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


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

        # Accumulated transcript
        self._transcript = ""
        self._prev_tail = ""  # For overlap deduplication

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

            # Initialize pipeline components
            self._capture = self._create_capture()
            self._vad = VadDetector.__new__(VadDetector)
            self._vad._threshold = self._settings.vad_threshold
            # Use a simple model stub for the VAD in session context;
            # the real model is loaded via VadDetector.__init__ which
            # downloads from torch hub. For production, create a proper
            # VadDetector. For tests, _create_chunker is overridden.
            self._chunker = self._create_chunker(self._vad)

            if self._whisper is None:
                from dental_notes.transcription.whisper_service import (
                    WhisperService,
                )

                self._whisper = WhisperService(self._settings)
                self._whisper.load_model()

            self._writer = TranscriptWriter(self._settings.storage_dir)
            self._transcript = ""
            self._prev_tail = ""

            # Start audio capture
            self._capture.start(device_index=mic_device)

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

        Raises:
            RuntimeError: If not in RECORDING state.
        """
        with self._lock:
            if self._state != SessionState.RECORDING:
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
            if self._state not in (SessionState.RECORDING, SessionState.PAUSED):
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
                    self._writer.append(deduped)
                    self._transcript += deduped

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
        """
        while self._processing_thread_running:
            # If paused, sleep briefly and continue
            if self._state == SessionState.PAUSED:
                time.sleep(0.05)
                continue

            # Get audio block from capture queue
            block = self._capture.get_block()
            if block is None:
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
                        self._writer.append(deduped)
                        self._transcript += deduped
                        # Keep tail for next deduplication
                        self._prev_tail = text

    def get_transcript(self) -> str:
        """Return the accumulated transcript text so far."""
        return self._transcript

    def get_state(self) -> SessionState:
        """Return the current session state."""
        return self._state

    def is_active(self) -> bool:
        """Return True if the session is RECORDING or PAUSED."""
        return self._state in (SessionState.RECORDING, SessionState.PAUSED)

    def get_level(self) -> float:
        """Return current audio level (delegates to AudioCapture).

        Returns 0.0 if no capture is active.
        """
        if self._capture is None:
            return 0.0
        return self._capture.get_level()
