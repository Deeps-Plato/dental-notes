"""Tests for dental_notes.audio.vad.VadDetector.

Uses FakeVadModel from conftest to avoid downloading the real silero-vad model.
"""

from unittest.mock import patch

import numpy as np
import pytest

from tests.conftest import FakeVadModel


class TestVadDetector:
    """Test VadDetector speech classification."""

    def test_is_speech_returns_true_for_speech_audio(self, mock_audio_speech: np.ndarray):
        """VadDetector.is_speech returns True for speech-like audio."""
        from dental_notes.audio.vad import VadDetector

        fake_model = FakeVadModel(probabilities=[0.9] * 100)
        with patch.object(VadDetector, "_load_model", return_value=fake_model):
            vad = VadDetector(threshold=0.5)
            assert vad.is_speech(mock_audio_speech) is True

    def test_is_speech_returns_false_for_silence(self, mock_audio_silence: np.ndarray):
        """VadDetector.is_speech returns False for silence."""
        from dental_notes.audio.vad import VadDetector

        fake_model = FakeVadModel(probabilities=[0.1] * 100)
        with patch.object(VadDetector, "_load_model", return_value=fake_model):
            vad = VadDetector(threshold=0.5)
            assert vad.is_speech(mock_audio_silence) is False

    def test_is_speech_returns_false_for_noise(self, mock_audio_noise: np.ndarray):
        """VadDetector.is_speech returns False for dental drill noise."""
        from dental_notes.audio.vad import VadDetector

        fake_model = FakeVadModel(probabilities=[0.3] * 100)
        with patch.object(VadDetector, "_load_model", return_value=fake_model):
            vad = VadDetector(threshold=0.5)
            assert vad.is_speech(mock_audio_noise) is False

    def test_threshold_is_configurable(self, mock_audio_speech: np.ndarray):
        """VadDetector uses configurable threshold."""
        from dental_notes.audio.vad import VadDetector

        # Probability 0.6 is above 0.5 threshold but below 0.7 threshold
        fake_model = FakeVadModel(probabilities=[0.6] * 100)

        with patch.object(VadDetector, "_load_model", return_value=fake_model):
            vad_low = VadDetector(threshold=0.5)
            assert vad_low.is_speech(mock_audio_speech) is True

        fake_model2 = FakeVadModel(probabilities=[0.6] * 100)
        with patch.object(VadDetector, "_load_model", return_value=fake_model2):
            vad_high = VadDetector(threshold=0.7)
            assert vad_high.is_speech(mock_audio_speech) is False

    def test_get_speech_probability(self, mock_audio_speech: np.ndarray):
        """get_speech_probability returns the max probability for the block."""
        from dental_notes.audio.vad import VadDetector

        fake_model = FakeVadModel(probabilities=[0.3, 0.8, 0.5])
        with patch.object(VadDetector, "_load_model", return_value=fake_model):
            vad = VadDetector(threshold=0.5)
            prob = vad.get_speech_probability(mock_audio_speech[:1536])
            assert prob == pytest.approx(0.8, abs=0.01)

    def test_reset_clears_model_state(self, mock_audio_speech: np.ndarray):
        """reset() resets VAD model state."""
        from dental_notes.audio.vad import VadDetector

        fake_model = FakeVadModel(probabilities=[0.9] * 100)
        with patch.object(VadDetector, "_load_model", return_value=fake_model):
            vad = VadDetector(threshold=0.5)
            vad.is_speech(mock_audio_speech[:512])
            vad.reset()
            # After reset, model state should be cleared
            # FakeVadModel.reset_states resets call index
            assert fake_model._call_index == 0
