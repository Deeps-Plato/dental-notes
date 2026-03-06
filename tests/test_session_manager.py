"""Tests for SessionManager state machine and processing pipeline.

Uses fake/mock versions of all dependencies (AudioCapture, WhisperService,
VadDetector, AudioChunker, TranscriptWriter) so tests run without GPU or mic.
"""

import importlib
import inspect
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from dental_notes.config import Settings


# --- Fakes ---


class FakeAudioCapture:
    """Fake AudioCapture that returns pre-loaded audio blocks."""

    def __init__(self, blocks: list[np.ndarray] | None = None):
        self._blocks = list(blocks or [])
        self._block_index = 0
        self._started = False
        self._stopped = False
        self._last_block: np.ndarray | None = None

    def start(self, device_index: int | None = None) -> None:
        self._started = True
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
        self._started = False

    def get_block(self) -> np.ndarray | None:
        if self._block_index < len(self._blocks):
            block = self._blocks[self._block_index]
            self._block_index += 1
            self._last_block = block
            return block
        return None

    def get_level(self) -> float:
        if self._last_block is None:
            return 0.0
        return float(np.sqrt(np.mean(self._last_block**2)))


class FakeWhisperService:
    """Fake WhisperService that returns configurable text."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or ["transcribed text"])
        self._call_index = 0
        self.transcribe_calls: list[np.ndarray] = []

    def transcribe(self, audio: np.ndarray) -> str:
        self.transcribe_calls.append(audio)
        if self._call_index < len(self._responses):
            text = self._responses[self._call_index]
            self._call_index += 1
            return text
        return ""

    @property
    def is_loaded(self) -> bool:
        return True

    def load_model(self) -> None:
        pass

    def unload(self) -> None:
        pass


class FakeChunker:
    """Fake AudioChunker that returns a chunk every N blocks."""

    def __init__(self, chunk_every: int = 3, chunk_data: np.ndarray | None = None):
        self._chunk_every = chunk_every
        self._chunk_data = chunk_data if chunk_data is not None else np.zeros(
            16000, dtype=np.float32
        )
        self._feed_count = 0

    def feed(self, audio_block: np.ndarray) -> np.ndarray | None:
        self._feed_count += 1
        if self._feed_count % self._chunk_every == 0:
            return self._chunk_data
        return None

    def flush(self) -> np.ndarray | None:
        if self._feed_count > 0 and self._feed_count % self._chunk_every != 0:
            return self._chunk_data
        return None


@pytest.fixture
def settings(tmp_path: Path):
    return Settings(storage_dir=tmp_path / "transcripts")


@pytest.fixture
def audio_blocks():
    """Pre-loaded audio blocks for testing."""
    return [np.random.default_rng(i).random(1600).astype(np.float32) for i in range(9)]


# --- State transition tests ---


class TestSessionStateTransitions:
    """SessionManager state machine transitions."""

    def test_initial_state_idle(self, settings):
        from dental_notes.session.manager import SessionManager, SessionState

        mgr = SessionManager(settings)
        assert mgr.get_state() == SessionState.IDLE

    def test_start_transitions_to_recording(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager, SessionState

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()
        mgr.start()
        assert mgr.get_state() == SessionState.RECORDING
        mgr.stop()

    def test_pause_transitions_to_paused(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager, SessionState

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()
        mgr.start()
        mgr.pause()
        assert mgr.get_state() == SessionState.PAUSED
        mgr.stop()

    def test_resume_transitions_to_recording(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager, SessionState

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()
        mgr.start()
        mgr.pause()
        mgr.resume()
        assert mgr.get_state() == SessionState.RECORDING
        mgr.stop()

    def test_stop_transitions_to_idle(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager, SessionState

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()
        mgr.start()
        result = mgr.stop()
        assert mgr.get_state() == SessionState.IDLE
        assert result is not None

    def test_stop_returns_transcript_path(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()
        mgr.start()
        result = mgr.stop()
        assert isinstance(result, Path)
        assert str(result).endswith(".txt")

    def test_invalid_transition_raises(self, settings):
        from dental_notes.session.manager import SessionManager

        mgr = SessionManager(settings)
        with pytest.raises(RuntimeError, match="Cannot pause"):
            mgr.pause()

    def test_double_start_raises(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()
        mgr.start()
        with pytest.raises(RuntimeError, match="Cannot start"):
            mgr.start()
        mgr.stop()


# --- Processing pipeline tests ---


class TestSessionProcessing:
    """SessionManager processing loop: audio -> chunks -> transcription."""

    def test_processing_loop_transcribes_chunks(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager

        whisper = FakeWhisperService(responses=["hello ", "world "])
        mgr = SessionManager(settings)
        mgr._whisper = whisper
        # FakeChunker returns a chunk every 3 blocks; 9 blocks -> 3 chunks
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker(chunk_every=3)
        mgr.start()

        # Give the processing thread time to consume all blocks
        time.sleep(0.5)
        mgr.stop()

        # Whisper should have been called at least once
        assert len(whisper.transcribe_calls) >= 1

    def test_transcript_accumulates(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager

        whisper = FakeWhisperService(responses=["hello ", "world "])
        mgr = SessionManager(settings)
        mgr._whisper = whisper
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker(chunk_every=3)
        mgr.start()

        time.sleep(0.5)
        mgr.stop()

        transcript = mgr.get_transcript()
        # At least some text should have accumulated
        assert len(transcript) > 0

    def test_is_active(self, settings, audio_blocks, tmp_path):
        from dental_notes.session.manager import SessionManager

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker()

        assert mgr.is_active() is False
        mgr.start()
        assert mgr.is_active() is True
        mgr.pause()
        assert mgr.is_active() is True  # PAUSED is still active
        mgr.resume()
        assert mgr.is_active() is True
        mgr.stop()
        assert mgr.is_active() is False

    def test_get_level_without_capture(self, settings):
        from dental_notes.session.manager import SessionManager

        mgr = SessionManager(settings)
        assert mgr.get_level() == 0.0


# --- Privacy and safety tests ---


class TestSessionPrivacyAndSafety:
    """Verify no network usage and audio is discarded."""

    def test_no_network(self):
        """Verify session/manager.py imports no network-related modules."""
        import dental_notes.session.manager as mgr_module

        source = inspect.getsource(mgr_module)

        # No network-related imports
        network_modules = [
            "urllib",
            "requests",
            "httpx",
            "aiohttp",
            "socket",
            "http.client",
        ]
        for mod in network_modules:
            assert f"import {mod}" not in source, (
                f"session/manager.py imports network module: {mod}"
            )

    def test_audio_discarded_after_transcription(
        self, settings, audio_blocks, tmp_path
    ):
        """Verify audio arrays are not stored in any SessionManager attribute."""
        from dental_notes.session.manager import SessionManager

        whisper = FakeWhisperService(responses=["hello "])
        mgr = SessionManager(settings)
        mgr._whisper = whisper
        mgr._create_capture = lambda: FakeAudioCapture(audio_blocks)
        mgr._create_chunker = lambda vad: FakeChunker(chunk_every=3)
        mgr.start()
        time.sleep(0.5)
        mgr.stop()

        # Check that no large numpy arrays are stored in the manager's attributes
        for attr_name in dir(mgr):
            if attr_name.startswith("__"):
                continue
            try:
                val = getattr(mgr, attr_name)
            except Exception:
                continue
            if isinstance(val, np.ndarray) and val.size > 100:
                pytest.fail(
                    f"SessionManager stores large audio array in attribute: {attr_name}"
                )
