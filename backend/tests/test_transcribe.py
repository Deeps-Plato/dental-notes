"""Tests for POST /transcribe."""

from unittest.mock import patch


def test_transcribe_success(client, tiny_wav):
    """Valid WAV → transcript response."""
    with patch(
        "dental_notes_backend.services.whisper_service.transcribe",
        return_value=("Tooth fourteen buccal three two four.", 1.5, "en"),
    ):
        resp = client.post(
            "/transcribe",
            files={"audio_file": ("test.wav", tiny_wav, "audio/wav")},
            data={"language": "en", "prompt": ""},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "Tooth fourteen buccal three two four."
    assert body["duration_seconds"] == 1.5
    assert body["language"] == "en"


def test_transcribe_oversized(client):
    """Files > 25 MB must be rejected with 413."""
    big_audio = b"0" * (25 * 1024 * 1024 + 1)
    resp = client.post(
        "/transcribe",
        files={"audio_file": ("big.wav", big_audio, "audio/wav")},
        data={"language": "en"},
    )
    assert resp.status_code == 413


def test_transcribe_whisper_not_loaded(client, tiny_wav):
    """503 when Whisper model isn't ready."""
    with patch(
        "dental_notes_backend.services.whisper_service.is_loaded",
        return_value=False,
    ):
        resp = client.post(
            "/transcribe",
            files={"audio_file": ("test.wav", tiny_wav, "audio/wav")},
            data={"language": "en"},
        )
    assert resp.status_code == 503


def test_transcribe_missing_file(client):
    """Missing audio_file → 422 validation error."""
    resp = client.post("/transcribe", data={"language": "en"})
    assert resp.status_code == 422
