"""Tests for SessionManager state machine and processing pipeline.

Uses fake/mock versions of all dependencies (AudioCapture, WhisperService,
VadDetector, AudioChunker, TranscriptWriter) so tests run without GPU or mic.

Fakes (FakeAudioCapture, FakeWhisperService, FakeChunker) are defined in
conftest.py and auto-discovered by pytest.
"""

import inspect
import time
from pathlib import Path

import numpy as np
import pytest

from dental_notes.config import Settings
from tests.conftest import FakeAudioCapture, FakeChunker, FakeWhisperService


@pytest.fixture
def settings(tmp_path: Path):
    return Settings(storage_dir=tmp_path / "transcripts")


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
