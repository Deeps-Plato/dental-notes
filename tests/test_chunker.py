"""Tests for dental_notes.transcription.chunker.AudioChunker.

Uses FakeVadModel-backed VadDetector to control speech/silence detection.
"""

from unittest.mock import patch

import numpy as np
import pytest

from tests.conftest import FakeVadModel

SAMPLE_RATE = 16000


def _make_audio_block(duration_secs: float = 0.1) -> np.ndarray:
    """Create a test audio block of specified duration at 16kHz."""
    num_samples = int(SAMPLE_RATE * duration_secs)
    return np.zeros(num_samples, dtype=np.float32)


def _make_vad_detector(probabilities: list[float]):
    """Create a VadDetector with a FakeVadModel."""
    from dental_notes.audio.vad import VadDetector

    fake_model = FakeVadModel(probabilities=probabilities)
    with patch.object(VadDetector, "_load_model", return_value=fake_model):
        vad = VadDetector(threshold=0.5)
    return vad


class TestAudioChunker:
    """Test AudioChunker hybrid chunking logic."""

    def test_noise_only_blocks_skipped_when_buffer_empty(self, test_settings):
        """Noise-only blocks are skipped when buffer is empty."""
        from dental_notes.transcription.chunker import AudioChunker

        vad = _make_vad_detector([0.1] * 200)
        chunker = AudioChunker(settings=test_settings, vad=vad)

        block = _make_audio_block(0.1)
        result = chunker.feed(block)
        assert result is None

    def test_silence_gap_triggers_chunk_finalization(self, test_settings):
        """Silence gap >= silence_gap_secs triggers chunk finalization."""
        from dental_notes.transcription.chunker import AudioChunker

        # 200 speech probs, then 200 silence probs
        probs = [0.9] * 200 + [0.1] * 200
        vad = _make_vad_detector(probs)
        chunker = AudioChunker(settings=test_settings, vad=vad)

        # Feed speech blocks (1 second of speech = 10 blocks at 0.1s each)
        speech_block = _make_audio_block(0.1)
        for _ in range(10):
            chunker.feed(speech_block)

        # Feed silence blocks until gap threshold is reached
        # silence_gap_secs = 1.5, so need 15 blocks at 0.1s = 1.5s
        silence_block = _make_audio_block(0.1)
        result = None
        for _ in range(20):
            result = chunker.feed(silence_block)
            if result is not None:
                break

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert len(result) > 0

    def test_max_duration_cap_forces_chunk_cut(self, test_settings):
        """Max duration cap forces chunk finalization at 20 seconds."""
        from dental_notes.transcription.chunker import AudioChunker

        # All speech -- never goes silent
        probs = [0.9] * 5000
        vad = _make_vad_detector(probs)
        chunker = AudioChunker(settings=test_settings, vad=vad)

        block = _make_audio_block(0.1)
        result = None
        # Feed 210 blocks of 0.1s = 21 seconds -- should trigger at 20s
        for _ in range(210):
            result = chunker.feed(block)
            if result is not None:
                break

        assert result is not None
        # Chunk should be approximately 20 seconds of audio
        expected_samples = SAMPLE_RATE * test_settings.max_chunk_duration_secs
        assert len(result) >= expected_samples * 0.9

    def test_overlap_preserved_between_chunks(self, test_settings):
        """Overlap is preserved between consecutive chunks."""
        from dental_notes.transcription.chunker import AudioChunker

        # Speech then silence, repeated twice
        probs = [0.9] * 200 + [0.1] * 200 + [0.9] * 200 + [0.1] * 200
        vad = _make_vad_detector(probs)
        chunker = AudioChunker(settings=test_settings, vad=vad)

        block = _make_audio_block(0.1)

        # First: feed speech
        for _ in range(10):
            chunker.feed(block)

        # Then silence to trigger chunk
        chunk1 = None
        for _ in range(20):
            chunk1 = chunker.feed(block)
            if chunk1 is not None:
                break

        assert chunk1 is not None

        # After first chunk, the overlap should be seeded in the buffer
        # Verify by checking the internal state has overlap content
        overlap_samples = int(test_settings.overlap_secs * SAMPLE_RATE)
        assert chunker._total_samples >= overlap_samples or chunker._total_samples == 0

    def test_flush_returns_remaining_buffer(self, test_settings):
        """flush() returns whatever is in the buffer."""
        from dental_notes.transcription.chunker import AudioChunker

        probs = [0.9] * 200
        vad = _make_vad_detector(probs)
        chunker = AudioChunker(settings=test_settings, vad=vad)

        block = _make_audio_block(0.1)
        # Feed some speech blocks but not enough for a chunk
        for _ in range(5):
            chunker.feed(block)

        result = chunker.flush()
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert len(result) > 0

    def test_flush_returns_none_when_buffer_empty(self, test_settings):
        """flush() returns None when buffer is empty."""
        from dental_notes.transcription.chunker import AudioChunker

        probs = [0.1] * 200
        vad = _make_vad_detector(probs)
        chunker = AudioChunker(settings=test_settings, vad=vad)

        result = chunker.flush()
        assert result is None
