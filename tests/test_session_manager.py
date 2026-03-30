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
from tests.conftest import (
    FakeAudioCapture,
    FakeChunker,
    FakeVadDetector,
    FakeWhisperService,
)


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


# --- Auto-pause and rolling buffer tests ---


def _make_silence_blocks(count: int, block_size: int = 1600) -> list[np.ndarray]:
    """Create `count` blocks of silence (zeros)."""
    return [np.zeros(block_size, dtype=np.float32) for _ in range(count)]


def _make_speech_blocks(count: int, block_size: int = 1600) -> list[np.ndarray]:
    """Create `count` blocks of speech-like audio (non-zero sine wave)."""
    return [
        np.sin(np.linspace(0, 2 * np.pi, block_size)).astype(np.float32)
        for _ in range(count)
    ]


class TestAutoPause:
    """AUTO_PAUSED state transitions and silence tracking."""

    def test_auto_paused_state_exists(self):
        """SessionState enum has AUTO_PAUSED value."""
        from dental_notes.session.manager import SessionState

        assert hasattr(SessionState, "AUTO_PAUSED")
        assert SessionState.AUTO_PAUSED.value == "auto_paused"

    def test_recording_to_auto_paused_on_silence(self, tmp_path):
        """RECORDING -> AUTO_PAUSED when silence exceeds threshold."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,  # 200ms -- very short for test speed
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        # Need enough silence blocks to exceed 0.2s at 100ms/block = 3 blocks
        # VAD: first few blocks are speech (to get past noise skip), then silence
        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        speech_blocks = _make_speech_blocks(2)
        silence_blocks = _make_silence_blocks(10)
        all_blocks = speech_blocks + silence_blocks

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)  # Never chunk
        mgr._vad_override = vad  # Will use this instead of real VAD

        mgr.start()
        time.sleep(0.8)  # Let processing loop consume blocks

        assert mgr.get_state() == SessionState.AUTO_PAUSED
        mgr.stop()

    def test_auto_pause_disabled(self, tmp_path):
        """No auto-pause when auto_pause_enabled=False."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.1,
            auto_pause_enabled=False,
            sample_rate=16000,
        )

        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        speech_blocks = _make_speech_blocks(2)
        silence_blocks = _make_silence_blocks(10)
        all_blocks = speech_blocks + silence_blocks

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.5)

        # Should still be RECORDING (or IDLE if blocks exhausted), NOT AUTO_PAUSED
        state = mgr.get_state()
        assert state != SessionState.AUTO_PAUSED
        mgr.stop()

    def test_auto_pause_to_recording_on_speech_resume(self, tmp_path):
        """AUTO_PAUSED -> RECORDING when 3+ consecutive speech blocks detected."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            rolling_buffer_secs=10.0,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        # Phase 1: speech then silence (triggers auto-pause)
        # Phase 2: speech resumes (triggers resume from auto-pause)
        vad_results = (
            [True, True]  # Initial speech
            + [False] * 5  # Silence -> auto-pause
            + [True] * 5  # Speech resume -> back to RECORDING
        )
        vad = FakeVadDetector(results=vad_results)

        speech = _make_speech_blocks(2)
        silence = _make_silence_blocks(5)
        speech_resume = _make_speech_blocks(5)
        all_blocks = speech + silence + speech_resume

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(1.0)  # Let loop process all blocks

        # After speech resumes, should be back in RECORDING
        assert mgr.get_state() == SessionState.RECORDING
        mgr.stop()

    def test_silence_tracking_resets_on_speech(self, tmp_path):
        """Silence duration resets to 0 when speech is detected during RECORDING."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.5,  # 500ms -- won't be reached
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        # Interleaving: speech, silence, speech, silence -- never enough consecutive silence
        vad_results = [True] * 3 + [False] * 2 + [True] * 3 + [False] * 2
        vad = FakeVadDetector(results=vad_results)

        blocks = _make_speech_blocks(3) + _make_silence_blocks(2) + _make_speech_blocks(3) + _make_silence_blocks(2)

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.5)

        # Should NOT have auto-paused because silence was interrupted by speech
        state = mgr.get_state()
        assert state != SessionState.AUTO_PAUSED
        mgr.stop()

    def test_stop_from_auto_paused(self, tmp_path):
        """stop() works from AUTO_PAUSED state."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        all_blocks = _make_speech_blocks(2) + _make_silence_blocks(10)

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.8)
        assert mgr.get_state() == SessionState.AUTO_PAUSED

        result = mgr.stop()
        assert mgr.get_state() == SessionState.IDLE
        assert isinstance(result, Path)

    def test_manual_pause_from_auto_paused(self, tmp_path):
        """pause() works from AUTO_PAUSED state."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        all_blocks = _make_speech_blocks(2) + _make_silence_blocks(10)

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.8)
        assert mgr.get_state() == SessionState.AUTO_PAUSED

        mgr.pause()
        assert mgr.get_state() == SessionState.PAUSED
        mgr.stop()

    def test_get_state_returns_auto_paused(self, tmp_path):
        """get_state() returns AUTO_PAUSED when in that state."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        all_blocks = _make_speech_blocks(2) + _make_silence_blocks(10)

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.8)

        assert mgr.get_state() == SessionState.AUTO_PAUSED
        mgr.stop()


class TestRollingBuffer:
    """Rolling buffer captures audio during AUTO_PAUSED and replays on resume."""

    def test_rolling_buffer_replayed_into_chunker_on_resume(self, tmp_path):
        """On resume from auto-pause, rolling buffer contents are fed to chunker."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            rolling_buffer_secs=10.0,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        # Phase 1: speech then silence -> auto-pause
        # Phase 2: 3+ speech blocks -> resume -> buffer replayed into chunker
        vad_results = (
            [True, True]  # Recording
            + [False] * 5  # Silence -> auto-pause
            + [True] * 5  # Auto-pause buffer -> resume
        )
        vad = FakeVadDetector(results=vad_results)

        speech = _make_speech_blocks(2)
        silence = _make_silence_blocks(5)
        speech_resume = _make_speech_blocks(5)
        all_blocks = speech + silence + speech_resume

        chunker = FakeChunker(chunk_every=100)  # Never auto-chunk
        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: chunker
        mgr._vad_override = vad

        mgr.start()
        time.sleep(1.0)

        # Chunker should have received feed() calls for the rolling buffer
        # blocks during resume, in addition to the normal recording blocks
        assert chunker._feed_count > len(speech)  # More than just initial speech
        mgr.stop()

    def test_rolling_buffer_cleared_on_auto_pause_entry(self, tmp_path):
        """Rolling buffer is cleared when entering AUTO_PAUSED to avoid
        replaying pre-pause audio that was already transcribed."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            rolling_buffer_secs=10.0,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        all_blocks = _make_speech_blocks(2) + _make_silence_blocks(10)

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.8)
        assert mgr.get_state() == SessionState.AUTO_PAUSED

        # Rolling buffer should only contain blocks added AFTER auto-pause started
        # (silence blocks in this case), NOT the speech blocks that were already
        # fed to the chunker during RECORDING
        buffer_len = len(mgr._rolling_buffer)
        # Buffer should contain some silence blocks (the ones after auto-pause)
        # but NOT the speech blocks from before
        assert buffer_len <= 10  # At most the silence blocks after transition
        mgr.stop()

    def test_is_active_includes_auto_paused(self, tmp_path):
        """is_active() returns True when AUTO_PAUSED."""
        from dental_notes.session.manager import SessionManager, SessionState

        settings = Settings(
            storage_dir=tmp_path / "transcripts",
            auto_pause_silence_secs=0.2,
            auto_pause_enabled=True,
            sample_rate=16000,
        )

        vad_results = [True, True] + [False] * 10
        vad = FakeVadDetector(results=vad_results)

        all_blocks = _make_speech_blocks(2) + _make_silence_blocks(10)

        mgr = SessionManager(settings)
        mgr._whisper = FakeWhisperService()
        mgr._create_capture = lambda: FakeAudioCapture(all_blocks)
        mgr._create_chunker = lambda v: FakeChunker(chunk_every=100)
        mgr._vad_override = vad

        mgr.start()
        time.sleep(0.8)
        assert mgr.get_state() == SessionState.AUTO_PAUSED
        assert mgr.is_active() is True
        mgr.stop()
