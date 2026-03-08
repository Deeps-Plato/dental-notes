"""Integration tests for FastAPI routes and SSE endpoint.

Uses httpx AsyncClient with ASGITransport for testing. SessionManager
is replaced with FakeSessionManager (from conftest) to avoid real
audio/GPU dependencies.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from dental_notes.main import create_app
from dental_notes.session.manager import SessionState


@pytest.fixture
def test_app(fake_session_manager):
    """Create a FastAPI app with overridden session manager (skip lifespan)."""
    app = create_app()
    # Override lifespan by directly setting state
    app.state.session_manager = fake_session_manager
    app.state.settings = None
    app.state.whisper_service = None
    return app


@pytest.fixture
async def client(test_app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_index_returns_200(client):
    """GET / returns 200 with HTML content."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Dental Notes" in response.text


@pytest.mark.asyncio
async def test_devices_returns_list(client):
    """GET /devices returns JSON list."""
    response = await client.get("/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_start_session(client, fake_session_manager):
    """POST /session/start returns 200 when idle."""
    assert fake_session_manager.get_state() == SessionState.IDLE
    response = await client.post("/session/start")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.RECORDING


@pytest.mark.asyncio
async def test_stop_session(client, fake_session_manager):
    """POST /session/stop returns 200 when recording."""
    fake_session_manager.start()
    assert fake_session_manager.get_state() == SessionState.RECORDING
    response = await client.post("/session/stop")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.IDLE


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(client, fake_session_manager):
    """POST /session/pause when idle returns 409."""
    assert fake_session_manager.get_state() == SessionState.IDLE
    response = await client.post("/session/pause")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_sse_stream_yields_transcript(test_app, fake_session_manager):
    """SSE generator yields transcript events with correct event types."""
    from dental_notes.ui.routes import session_stream

    fake_session_manager._state = SessionState.RECORDING
    fake_session_manager._chunks = [("Doctor", "test transcript text")]
    fake_session_manager._level = 0.5

    # Create a mock request
    mock_request = AsyncMock()
    mock_request.app = test_app
    mock_request.is_disconnected = AsyncMock(return_value=False)

    response = await session_stream(mock_request)

    # EventSourceResponse wraps the generator -- get events from it
    # We test the generator directly by extracting it
    generator = response.body_iterator

    events = []
    count = 0
    async for event in generator:
        events.append(event)
        count += 1
        # After getting a few events, simulate session end
        if count >= 2:
            fake_session_manager._state = SessionState.IDLE
        if count >= 4:
            break

    # Should have gotten transcript and level events
    assert len(events) >= 2


@pytest.mark.asyncio
async def test_status_endpoint(client, fake_session_manager):
    """GET /session/status returns correct state JSON."""
    response = await client.get("/session/status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "idle"
    assert "chunk_count" in data
    assert "level" in data


@pytest.mark.asyncio
async def test_pause_and_resume(client, fake_session_manager):
    """Full lifecycle: start -> pause -> resume -> stop."""
    # Start
    response = await client.post("/session/start")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.RECORDING

    # Pause
    response = await client.post("/session/pause")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.PAUSED

    # Resume
    response = await client.post("/session/resume")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.RECORDING

    # Stop
    response = await client.post("/session/stop")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.IDLE


@pytest.mark.asyncio
async def test_start_with_device(client, fake_session_manager):
    """POST /session/start with device form field."""
    response = await client.post(
        "/session/start",
        data={"device": "0"},
    )
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.RECORDING


@pytest.mark.asyncio
async def test_start_error_shows_banner(client, fake_session_manager):
    """POST /session/start with hardware error returns error banner HTML."""

    def exploding_start(mic_device=None):
        raise OSError("No audio device available")

    fake_session_manager.start = exploding_start
    response = await client.post("/session/start")
    assert response.status_code == 500
    assert "error-banner" in response.text
    assert "No audio device available" in response.text
    # Should still show the Start button for retry
    assert "Start Recording" in response.text


@pytest.mark.asyncio
async def test_stop_shows_transcript_path(client, fake_session_manager):
    """POST /session/stop shows the saved transcript file path."""
    fake_session_manager.start()
    response = await client.post("/session/stop")
    assert response.status_code == 200
    assert "test-transcript.txt" in response.text


@pytest.mark.asyncio
async def test_recording_state_shows_pause_stop(client, fake_session_manager):
    """Recording state HTML includes Pause and Stop buttons."""
    response = await client.post("/session/start")
    assert response.status_code == 200
    assert "Pause" in response.text
    assert "Stop" in response.text
    assert "Recording" in response.text


@pytest.mark.asyncio
async def test_paused_state_shows_resume_stop(client, fake_session_manager):
    """Paused state HTML includes Resume and Stop buttons."""
    fake_session_manager.start()
    response = await client.post("/session/pause")
    assert response.status_code == 200
    assert "Resume" in response.text
    assert "Stop" in response.text
    assert "Paused" in response.text


@pytest.mark.asyncio
async def test_index_has_mic_selector(client):
    """Homepage includes the microphone selector dropdown."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'id="mic-select"' in response.text
    assert "Default device" in response.text


@pytest.mark.asyncio
async def test_index_has_level_bar(client):
    """Homepage includes the audio level indicator."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'id="level-bar"' in response.text


@pytest.mark.asyncio
async def test_index_has_transcript_area(client):
    """Homepage includes the transcript display area."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'id="transcript-area"' in response.text
    assert "No transcript yet" in response.text


@pytest.mark.asyncio
async def test_stop_preserves_transcript_with_speaker_labels(
    client, fake_session_manager
):
    """After stop, transcript is rendered with speaker labels and chunk divs."""
    fake_session_manager.start()
    fake_session_manager._chunks = [
        ("Doctor", "I see the MOD amalgam on tooth 14 has a fracture"),
        ("Patient", "Is that something that needs to be fixed right away"),
    ]
    response = await client.post("/session/stop")
    assert response.status_code == 200
    # Chunks should be rendered as HTML divs with speaker labels
    assert "Doctor:" in response.text
    assert "Patient:" in response.text
    assert "MOD amalgam" in response.text
    assert "fixed right away" in response.text
    assert 'class="chunk"' in response.text


@pytest.mark.asyncio
async def test_sse_sends_chunk_divs(test_app, fake_session_manager):
    """SSE transcript events contain div.chunk elements with speaker labels."""
    from dental_notes.ui.routes import session_stream

    fake_session_manager._state = SessionState.RECORDING
    fake_session_manager._chunks = [
        ("Doctor", "Crown prep on tooth 14"),
    ]
    fake_session_manager._level = 0.3

    mock_request = AsyncMock()
    mock_request.app = test_app
    mock_request.is_disconnected = AsyncMock(return_value=False)

    response = await session_stream(mock_request)
    generator = response.body_iterator

    events = []
    count = 0
    async for event in generator:
        events.append(event)
        count += 1
        if count >= 2:
            fake_session_manager._state = SessionState.IDLE
        if count >= 4:
            break

    # Find the transcript event and verify it has the chunk HTML
    event_data = "".join(e.data for e in events if hasattr(e, "data"))
    assert "Doctor:" in event_data
    assert "chunk" in event_data
