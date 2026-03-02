"""Tests for GET /health."""

from unittest.mock import patch


def test_health_ok(client):
    with patch("dental_notes_backend.services.whisper_service.is_loaded", return_value=True):
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "whisper_loaded" in body
    assert "model_size" in body


def test_health_no_auth_required(client):
    """Health endpoint must be reachable without an API key."""
    resp = client.get("/health", headers={"X-API-Key": ""})
    # Still 200 — /health is in the open-path list
    assert resp.status_code == 200


def test_protected_route_requires_key(client):
    """Sending wrong key to /transcribe should yield 401."""
    resp = client.post(
        "/transcribe",
        headers={"X-API-Key": "wrong-key"},
        files={"audio_file": ("test.wav", b"data", "audio/wav")},
    )
    assert resp.status_code == 401
