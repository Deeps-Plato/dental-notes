"""Shared test fixtures."""

import io
import struct
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Patch Whisper before app import so the model is never loaded in tests
_mock_whisper = MagicMock()
_mock_whisper.is_loaded.return_value = True


@pytest.fixture(autouse=True)
def _patch_whisper(monkeypatch):
    """Prevent actual Whisper model loading during tests."""
    with patch("dental_notes_backend.services.whisper_service._model", new=MagicMock()):
        yield


@pytest.fixture()
def client():
    """TestClient with Whisper loading mocked out."""
    with patch("dental_notes_backend.services.whisper_service.load_model"):
        with patch("dental_notes_backend.services.whisper_service.unload_model"):
            from dental_notes_backend.main import create_app

            app = create_app()
            with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
                yield c


@pytest.fixture()
def tiny_wav() -> bytes:
    """Return a minimal valid WAV file (100ms of silence at 16kHz mono)."""
    sample_rate = 16000
    n_samples = sample_rate // 10  # 100ms
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))
    return buf.getvalue()
