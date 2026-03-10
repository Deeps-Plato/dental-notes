"""Tests for dictation endpoint: field-level mic-to-text via Whisper.

Tests the POST /dictate endpoint which accepts audio data (raw PCM bytes),
transcribes via WhisperService, and returns JSON with transcribed text.
"""

import struct

import pytest
from httpx import ASGITransport, AsyncClient

from dental_notes.main import create_app


def _make_pcm_bytes(num_samples: int = 1600) -> bytes:
    """Create raw PCM 16-bit little-endian audio bytes for testing.

    Generates a simple sine-like pattern so it's not all zeros.
    """
    samples = []
    for i in range(num_samples):
        # Simple triangle wave
        value = int(((i % 160) / 160.0 - 0.5) * 32000)
        samples.append(value)
    return struct.pack(f"<{num_samples}h", *samples)


@pytest.fixture
def dictation_app(fake_session_manager):
    """FastAPI app configured for dictation endpoint tests."""
    from tests.conftest import FakeWhisperService

    app = create_app()
    app.state.session_manager = fake_session_manager

    # Use FakeWhisperService that returns canned text
    whisper = FakeWhisperService(responses=["Patient reports sensitivity"])
    app.state.whisper_service = whisper
    app.state.settings = None

    # Provide minimal session_store and clinical_extractor
    from tests.conftest import FakeSessionStore

    app.state.session_store = FakeSessionStore()
    app.state.clinical_extractor = None

    return app


@pytest.fixture
async def dictation_client(dictation_app):
    """Async HTTP client for dictation route tests."""
    transport = ASGITransport(app=dictation_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- POST /dictate ---


@pytest.mark.asyncio
async def test_dictate_returns_transcribed_text(dictation_client):
    """POST /dictate with audio bytes returns transcribed text as JSON."""
    audio_bytes = _make_pcm_bytes(1600)
    response = await dictation_client.post(
        "/dictate",
        content=audio_bytes,
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert data["text"] == "Patient reports sensitivity"


@pytest.mark.asyncio
async def test_dictate_returns_503_when_whisper_not_loaded(dictation_client, dictation_app):
    """POST /dictate returns 503 if Whisper model is not loaded."""
    # Replace with a whisper service that reports not loaded
    class UnloadedWhisper:
        @property
        def is_loaded(self) -> bool:
            return False

        def transcribe(self, audio):
            raise RuntimeError("Model not loaded")

    dictation_app.state.whisper_service = UnloadedWhisper()

    audio_bytes = _make_pcm_bytes(1600)
    response = await dictation_client.post(
        "/dictate",
        content=audio_bytes,
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 503
    data = response.json()
    assert "not available" in data["detail"].lower() or "gpu" in data["detail"].lower()


@pytest.mark.asyncio
async def test_dictate_empty_audio_returns_empty_text(dictation_client, dictation_app):
    """POST /dictate with empty body returns empty text."""
    # Replace whisper to return empty for empty audio
    from tests.conftest import FakeWhisperService

    dictation_app.state.whisper_service = FakeWhisperService(responses=[""])

    response = await dictation_client.post(
        "/dictate",
        content=b"",
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == ""
