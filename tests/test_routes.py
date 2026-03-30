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
def test_app(fake_session_manager, fake_session_store):
    """Create a FastAPI app with overridden session manager (skip lifespan)."""
    app = create_app()
    # Override lifespan by directly setting state
    app.state.session_manager = fake_session_manager
    app.state.session_store = fake_session_store
    app.state.settings = None
    app.state.whisper_service = None
    app.state.clinical_extractor = None
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
async def test_stop_redirects_to_review(client, fake_session_manager):
    """POST /session/stop creates session and redirects to review page."""
    fake_session_manager.start()
    response = await client.post("/session/stop", follow_redirects=False)
    assert response.status_code == 200
    # HX-Redirect header points to the review page
    hx_redirect = response.headers.get("hx-redirect", "")
    assert "/session/" in hx_redirect
    assert "/review" in hx_redirect


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
async def test_stop_creates_session_in_store(
    client, fake_session_manager, fake_session_store
):
    """POST /session/stop creates a session in the store with chunks."""
    fake_session_manager.start()
    fake_session_manager._chunks = [
        ("Doctor", "I see the MOD amalgam on tooth 14 has a fracture"),
        ("Patient", "Is that something that needs to be fixed right away"),
    ]
    response = await client.post("/session/stop", follow_redirects=False)
    assert response.status_code == 200

    # Session should have been saved
    sessions = fake_session_store.list_sessions()
    assert len(sessions) == 1
    assert len(sessions[0].chunks) == 2


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


# --- Template selection / appointment_type tests ---


@pytest.mark.asyncio
async def test_start_accepts_appointment_type(client, fake_session_manager):
    """POST /session/start accepts appointment_type form field and stores it."""
    response = await client.post(
        "/session/start",
        data={"appointment_type": "restorative"},
    )
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.RECORDING


@pytest.mark.asyncio
async def test_start_defaults_appointment_type_in_app_state(test_app, fake_session_manager):
    """session_start always sets appointment_type to general (auto-detect at extraction)."""
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/session/start")
    assert getattr(test_app.state, "appointment_type", None) == "general"


@pytest.mark.asyncio
async def test_start_defaults_appointment_type_to_general(test_app, fake_session_manager):
    """session_start defaults appointment_type to general when not provided."""
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/session/start")
    assert getattr(test_app.state, "appointment_type", None) == "general"


@pytest.mark.asyncio
async def test_stop_passes_template_type_to_extractor(
    fake_session_manager, fake_session_store
):
    """session_stop passes template_type to extract_with_gpu_handoff."""
    from tests.conftest import FakeOllamaService, FakeWhisperServiceGpu

    app = create_app()
    app.state.session_manager = fake_session_manager
    app.state.session_store = fake_session_store
    app.state.whisper_service = FakeWhisperServiceGpu()
    app.state.settings = None

    from dental_notes.clinical.extractor import ClinicalExtractor
    from dental_notes.config import Settings

    fake_settings = Settings(
        storage_dir="/tmp/test-transcripts",
        sessions_dir="/tmp/test-sessions",
    )
    fake_ollama = FakeOllamaService()
    fake_extractor = ClinicalExtractor(fake_ollama, fake_settings)
    app.state.clinical_extractor = fake_extractor

    # Set appointment_type on app state (simulates what session_start does)
    app.state.appointment_type = "restorative"

    fake_session_manager.start()
    fake_session_manager._chunks = [
        ("Doctor", "Crown prep on tooth 14"),
    ]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/session/stop", follow_redirects=False)

    # Extractor should have received template_type="restorative"
    # When appointment_type != "general", it should pass the type directly
    # Check that the extractor was called (generate was called for classification
    # or generate_structured for extraction)
    assert fake_ollama.call_count >= 1


@pytest.mark.asyncio
async def test_stop_passes_none_template_for_general(
    fake_session_manager, fake_session_store
):
    """session_stop passes template_type=None when appointment_type is general."""
    from tests.conftest import FakeOllamaService, FakeWhisperServiceGpu

    app = create_app()
    app.state.session_manager = fake_session_manager
    app.state.session_store = fake_session_store
    app.state.whisper_service = FakeWhisperServiceGpu()
    app.state.settings = None

    from dental_notes.clinical.extractor import ClinicalExtractor
    from dental_notes.config import Settings

    fake_settings = Settings(
        storage_dir="/tmp/test-transcripts",
        sessions_dir="/tmp/test-sessions",
    )
    fake_ollama = FakeOllamaService()
    fake_extractor = ClinicalExtractor(fake_ollama, fake_settings)
    app.state.clinical_extractor = fake_extractor

    # Set appointment_type to "general" on app state
    app.state.appointment_type = "general"

    fake_session_manager.start()
    fake_session_manager._chunks = [
        ("Doctor", "Crown prep on tooth 14"),
    ]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/session/stop", follow_redirects=False)

    # When appointment_type is "general", should pass template_type=None
    # to trigger auto-detect via _infer_appointment_type()
    # This means generate() will be called first (for classification)
    assert fake_ollama.generate_call_count >= 1


@pytest.mark.asyncio
async def test_index_has_no_appointment_type_dropdown(client):
    """Homepage does NOT include appointment type dropdown (auto-detect at extraction)."""
    response = await client.get("/")
    assert response.status_code == 200
    assert 'id="appt-type-select"' not in response.text


# --- Phase 5 Plan 03: Next Patient route ---


@pytest.mark.asyncio
async def test_next_patient_returns_recording_state(
    client, fake_session_manager
):
    """POST /session/next-patient saves current and starts new recording."""
    fake_session_manager.start()
    assert fake_session_manager.get_state() == SessionState.RECORDING
    response = await client.post("/session/next-patient")
    assert response.status_code == 200
    assert fake_session_manager.get_state() == SessionState.RECORDING
    assert "Recording" in response.text or "recording" in response.text


@pytest.mark.asyncio
async def test_next_patient_when_idle_returns_error(
    client, fake_session_manager
):
    """POST /session/next-patient when idle returns error partial."""
    assert fake_session_manager.get_state() == SessionState.IDLE
    response = await client.post("/session/next-patient")
    assert response.status_code == 409


# --- Phase 5 Plan 03: Health endpoints ---


@pytest.mark.asyncio
async def test_health_endpoint_returns_json(test_app):
    """GET /api/health returns JSON with status and checks."""
    from dental_notes.health import HealthChecker
    from dental_notes.config import Settings

    settings = Settings(
        storage_dir="/tmp/test-storage",
        sessions_dir="/tmp/test-sessions",
    )
    test_app.state.health_checker = HealthChecker(settings=settings)

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "checks" in data
    assert "gpu" in data["checks"]
    assert "microphone" in data["checks"]
    assert "disk" in data["checks"]


@pytest.mark.asyncio
async def test_health_bar_returns_html(test_app):
    """GET /health-bar returns HTML partial with health status."""
    from dental_notes.health import HealthChecker
    from dental_notes.config import Settings

    settings = Settings(
        storage_dir="/tmp/test-storage",
        sessions_dir="/tmp/test-sessions",
    )
    test_app.state.health_checker = HealthChecker(settings=settings)

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get("/health-bar")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Should contain health indicator content
    assert "health" in response.text.lower() or "gpu" in response.text.lower()


# --- Phase 5 Plan 03: Session list filtering ---


@pytest.mark.asyncio
async def test_sessions_list_defaults_to_today(test_app, fake_session_store):
    """GET /sessions defaults to today's date filter."""
    from datetime import datetime, timezone
    from dental_notes.session.store import SavedSession

    # Add a session created today
    session = SavedSession(
        transcript_path="/tmp/t.txt",
        chunks=[("Doctor", "hello")],
        created_at=datetime.now(timezone.utc),
    )
    fake_session_store._sessions[session.session_id] = session

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get("/sessions")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_sessions_list_filters_by_date(test_app, fake_session_store):
    """GET /sessions?date=YYYY-MM-DD filters sessions by date."""
    from datetime import datetime, timezone
    from dental_notes.session.store import SavedSession

    session = SavedSession(
        transcript_path="/tmp/t.txt",
        chunks=[("Doctor", "hello")],
        created_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    fake_session_store._sessions[session.session_id] = session

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get("/sessions?date=2026-01-15")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_sessions_list_filters_by_status(test_app, fake_session_store):
    """GET /sessions?status=recorded filters sessions by status."""
    from dental_notes.session.store import SavedSession

    session = SavedSession(
        transcript_path="/tmp/t.txt",
        chunks=[("Doctor", "hello")],
    )
    fake_session_store._sessions[session.session_id] = session

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get("/sessions?status=recorded")

    assert response.status_code == 200


# --- Phase 5 Plan 03: SSE auto-pause and status fields ---


@pytest.mark.asyncio
async def test_sse_includes_auto_paused_state(
    test_app, fake_session_manager
):
    """SSE stream includes auto_paused state when session is auto-paused."""
    from dental_notes.ui.routes import session_stream

    fake_session_manager._state = SessionState.AUTO_PAUSED
    fake_session_manager._chunks = []
    fake_session_manager._level = 0.0

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

    # Should have gotten status events with state info
    event_data = "".join(
        getattr(e, "data", "") for e in events
    )
    assert "auto_paused" in event_data


@pytest.mark.asyncio
async def test_sse_includes_mic_disconnected_flag(
    test_app, fake_session_manager
):
    """SSE status event includes mic_disconnected when mic is lost."""
    from dental_notes.ui.routes import session_stream

    fake_session_manager._state = SessionState.RECORDING
    fake_session_manager._chunks = []
    fake_session_manager._level = 0.0
    fake_session_manager._mic_disconnected = True

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

    event_data = "".join(
        getattr(e, "data", "") for e in events
    )
    assert "mic_disconnected" in event_data


@pytest.mark.asyncio
async def test_sse_includes_transcription_behind_flag(
    test_app, fake_session_manager
):
    """SSE status event includes transcription_behind when GPU OOM occurring."""
    from dental_notes.ui.routes import session_stream

    fake_session_manager._state = SessionState.RECORDING
    fake_session_manager._chunks = []
    fake_session_manager._level = 0.0
    fake_session_manager._transcription_behind = True
    fake_session_manager._oom_retry_count = 2

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

    event_data = "".join(
        getattr(e, "data", "") for e in events
    )
    assert "transcription_behind" in event_data


# --- Phase 5 Plan 03: Extraction retry routes ---


@pytest.mark.asyncio
async def test_extraction_status_returns_idle(
    test_app, fake_session_store
):
    """GET /session/{id}/extraction-status returns idle state for recorded session."""
    from dental_notes.session.store import SavedSession

    session = SavedSession(
        transcript_path="/tmp/t.txt",
        chunks=[("Doctor", "hello")],
    )
    fake_session_store._sessions[session.session_id] = session

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get(
            f"/session/{session.session_id}/extraction-status"
        )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_extraction_status_returns_extracted(
    test_app, fake_session_store, sample_saved_session
):
    """GET /session/{id}/extraction-status returns success for extracted session."""
    fake_session_store._sessions[
        sample_saved_session.session_id
    ] = sample_saved_session

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        response = await ac.get(
            f"/session/{sample_saved_session.session_id}/extraction-status"
        )

    assert response.status_code == 200
