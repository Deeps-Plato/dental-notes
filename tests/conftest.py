"""Shared test fixtures for dental-notes v2."""

from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def test_settings(tmp_path: Path):
    """Settings with a tmp_path storage_dir for test isolation."""
    from dental_notes.config import Settings

    return Settings(storage_dir=tmp_path / "transcripts")


@pytest.fixture
def mock_audio_speech() -> np.ndarray:
    """1 second of speech-like audio: 440Hz sine wave at 16kHz sample rate."""
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def mock_audio_silence() -> np.ndarray:
    """1 second of silence: near-zero values at 16kHz sample rate."""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def mock_audio_noise() -> np.ndarray:
    """1 second of noise simulating dental drill: random values at 16kHz."""
    rng = np.random.default_rng(seed=42)
    return (rng.random(16000) * 0.1).astype(np.float32)


class FakeVadModel:
    """Mock silero-vad model for testing without downloading the real model.

    Returns configurable speech probabilities for each call.
    """

    def __init__(self, probabilities: list[float] | None = None):
        self._probabilities = probabilities or []
        self._call_index = 0

    def __call__(self, audio_chunk, sample_rate: int) -> "FakeTensor":
        if self._call_index < len(self._probabilities):
            prob = self._probabilities[self._call_index]
            self._call_index += 1
        else:
            prob = 0.0
        return FakeTensor(prob)

    def reset_states(self) -> None:
        """Reset model state (mirrors silero-vad API)."""
        self._call_index = 0


class FakeTensor:
    """Minimal tensor-like object that supports .item()."""

    def __init__(self, value: float):
        self._value = value

    def item(self) -> float:
        return self._value


@pytest.fixture
def fake_vad_speech() -> FakeVadModel:
    """FakeVadModel that always returns high speech probability."""
    return FakeVadModel(probabilities=[0.9] * 100)


@pytest.fixture
def fake_vad_silence() -> FakeVadModel:
    """FakeVadModel that always returns low speech probability."""
    return FakeVadModel(probabilities=[0.1] * 100)
