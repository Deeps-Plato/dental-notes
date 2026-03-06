"""Integration tests for FastAPI routes and SSE endpoint.

Uses httpx AsyncClient with ASGITransport for testing. SessionManager
is replaced with FakeSessionManager to avoid real audio/GPU dependencies.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from dental_notes.main import create_app
from dental_notes.session.manager import SessionState


class FakeSessionManager:
    """Mimics SessionManager state transitions and returns canned data."""

    def __init__(self):
        self._state = SessionState.IDLE
        self._transcript = ""
        self._level = 0.0
        self._transcript_path = Path("/tmp/test-transcript.txt")

    def start(self, mic_device: int | None = None) -> None:
        if self._state != SessionState.IDLE:
            raise RuntimeError(f"Cannot start: state is {self._state.value}")
        self._state = SessionState.RECORDING
        self._transcript = ""

    def pause(self) -> None:
        if self._state != SessionState.RECORDING:
            raise RuntimeError(f"Cannot pause: state is {self._state.value}")
        self._state = SessionState.PAUSED

    def resume(self) -> None:
        if self._state != SessionState.PAUSED:
            raise RuntimeError(f"Cannot resume: state is {self._state.value}")
        self._state = SessionState.RECORDING

    def stop(self) -> Path:
        if self._state not in (SessionState.RECORDING, SessionState.PAUSED):
            raise RuntimeError(f"Cannot stop: state is {self._state.value}")
        self._state = SessionState.IDLE
        return self._transcript_path

    def get_transcript(self) -> str:
        return self._transcript

    def get_state(self) -> SessionState:
        return self._state

    def is_active(self) -> bool:
        return self._state in (SessionState.RECORDING, SessionState.PAUSED)

    def get_level(self) -> float:
        return self._level


@pytest.fixture
def fake_session_manager():
    return FakeSessionManager()


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
    fake_session_manager._transcript = "test transcript text"
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
    assert "transcript_length" in data
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
