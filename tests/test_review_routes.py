"""Tests for review workflow routes: session review, extraction, save, finalize, session list.

Tests all review UI routes using FakeSessionStore and FakeOllamaService
(no real Ollama or GPU). Covers the full review workflow from session stop
through finalization.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from dental_notes.main import create_app
from dental_notes.session.manager import SessionState


@pytest.fixture
def review_app(fake_session_manager, fake_session_store, sample_saved_session):
    """FastAPI app with session_store, fake extractor, and fake session manager."""
    from tests.conftest import FakeOllamaService, FakeWhisperServiceGpu

    app = create_app()
    app.state.session_manager = fake_session_manager
    app.state.session_store = fake_session_store
    app.state.whisper_service = FakeWhisperServiceGpu()
    app.state.settings = None

    # Create a fake ClinicalExtractor using FakeOllamaService
    from dental_notes.clinical.extractor import ClinicalExtractor
    from dental_notes.config import Settings

    fake_settings = Settings(
        storage_dir="/tmp/test-transcripts",
        sessions_dir="/tmp/test-sessions",
    )
    fake_extractor = ClinicalExtractor(FakeOllamaService(), fake_settings)
    app.state.clinical_extractor = fake_extractor

    # Pre-populate a session for review tests
    fake_session_store._sessions[sample_saved_session.session_id] = (
        sample_saved_session
    )

    return app


@pytest.fixture
async def review_client(review_app):
    """Async HTTP client for review route tests."""
    transport = ASGITransport(app=review_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- GET /session/{session_id}/review ---


@pytest.mark.asyncio
async def test_review_page_returns_200(review_client, sample_saved_session):
    """GET /session/{id}/review returns 200 with review page HTML."""
    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_review_page_contains_transcript(
    review_client, sample_saved_session
):
    """Review page includes the transcript text from chunks."""
    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "Good morning" in response.text
    assert "sensitive to cold" in response.text


@pytest.mark.asyncio
async def test_review_page_contains_soap_sections(
    review_client, sample_saved_session
):
    """Review page includes SOAP note section content."""
    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "cold sensitivity" in response.text.lower() or "Class II caries" in response.text


@pytest.mark.asyncio
async def test_review_page_not_found(review_client):
    """GET /session/nonexistent/review returns 404."""
    response = await review_client.get("/session/nonexistent-id/review")
    assert response.status_code == 404


# --- POST /session/stop (modified to include session creation + extraction) ---


@pytest.mark.asyncio
async def test_stop_creates_session_and_redirects(
    review_client, fake_session_manager, fake_session_store
):
    """POST /session/stop creates a session, extracts, and redirects to review."""
    fake_session_manager.start()
    fake_session_manager._chunks = [
        ("Doctor", "Good morning"),
        ("Patient", "My tooth hurts"),
    ]

    response = await review_client.post(
        "/session/stop", follow_redirects=False
    )
    # Should return with HX-Redirect header pointing to review page
    assert response.status_code == 200
    hx_redirect = response.headers.get("hx-redirect", "")
    assert "/session/" in hx_redirect
    assert "/review" in hx_redirect

    # Session should have been created in the store
    sessions = fake_session_store.list_sessions()
    assert len(sessions) >= 1


# --- POST /session/{session_id}/extract ---


@pytest.mark.asyncio
async def test_extract_returns_note_html(
    review_client, sample_saved_session
):
    """POST /session/{id}/extract re-extracts and returns note panel HTML."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/extract"
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_extract_updates_session(
    review_client, sample_saved_session, fake_session_store
):
    """Extraction updates the session's extraction_result."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/extract"
    )
    assert response.status_code == 200

    session = fake_session_store.get_session(sample_saved_session.session_id)
    assert session is not None
    assert session.extraction_result is not None
    assert session.transcript_dirty is False


@pytest.mark.asyncio
async def test_extract_not_found(review_client):
    """POST /session/nonexistent/extract returns 404."""
    response = await review_client.post("/session/nonexistent-id/extract")
    assert response.status_code == 404


# --- POST /session/{session_id}/save ---


@pytest.mark.asyncio
async def test_save_persists_edited_note(
    review_client, sample_saved_session, fake_session_store
):
    """POST /session/{id}/save stores edited note fields."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/save",
        data={
            "subjective": "Updated subjective",
            "objective": "Updated objective",
            "assessment": "Updated assessment",
            "plan": "Updated plan",
            "cdt_codes": "D2392 - Composite\nD0220 - Radiograph",
            "clinical_discussion": "- Updated discussion",
            "medications": "- Amoxicillin 500mg",
            "transcript": "Doctor: Updated transcript",
        },
    )
    assert response.status_code == 200

    session = fake_session_store.get_session(sample_saved_session.session_id)
    assert session is not None
    assert session.edited_note is not None
    assert session.edited_note["subjective"] == "Updated subjective"


@pytest.mark.asyncio
async def test_save_sets_reviewed_status(
    review_client, sample_saved_session, fake_session_store
):
    """Save sets session status to REVIEWED."""
    from dental_notes.session.store import SessionStatus

    await review_client.post(
        f"/session/{sample_saved_session.session_id}/save",
        data={
            "subjective": "S",
            "objective": "O",
            "assessment": "A",
            "plan": "P",
            "cdt_codes": "",
            "clinical_discussion": "",
            "medications": "",
            "transcript": "text",
        },
    )

    session = fake_session_store.get_session(sample_saved_session.session_id)
    assert session.status == SessionStatus.REVIEWED


# --- POST /session/{session_id}/finalize ---


@pytest.mark.asyncio
async def test_finalize_deletes_session(
    review_client, sample_saved_session, fake_session_store
):
    """POST /session/{id}/finalize removes the session."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/finalize"
    )
    assert response.status_code == 200

    session = fake_session_store.get_session(sample_saved_session.session_id)
    assert session is None


@pytest.mark.asyncio
async def test_finalize_returns_confirmation_html(
    review_client, sample_saved_session
):
    """Finalize returns confirmation HTML with links."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/finalize"
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Should contain link to start new session or go to session list
    assert "New Session" in response.text or "session" in response.text.lower()


# --- GET /sessions ---


@pytest.mark.asyncio
async def test_sessions_list_returns_200(review_client):
    """GET /sessions returns 200 with session list page."""
    response = await review_client.get("/sessions")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_sessions_list_contains_sessions(
    review_client, sample_saved_session
):
    """Session list shows saved sessions."""
    response = await review_client.get("/sessions")
    assert response.status_code == 200
    # Should contain session ID or timestamp
    assert sample_saved_session.session_id in response.text or "sample" in response.text.lower()


# --- GET /api/session/{session_id}/note-text ---


@pytest.mark.asyncio
async def test_note_text_returns_formatted_text(
    review_client, sample_saved_session
):
    """GET /api/session/{id}/note-text returns formatted clipboard text."""
    response = await review_client.get(
        f"/api/session/{sample_saved_session.session_id}/note-text"
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # Should contain SOAP section headers
    assert "Subjective" in response.text
    assert "Objective" in response.text
    assert "Assessment" in response.text
    assert "Plan" in response.text


@pytest.mark.asyncio
async def test_note_text_not_found(review_client):
    """GET /api/session/nonexistent/note-text returns 404."""
    response = await review_client.get("/api/session/nonexistent-id/note-text")
    assert response.status_code == 404


# --- Extraction error handling ---


@pytest.mark.asyncio
async def test_extract_error_returns_error_html(review_client, review_app, sample_saved_session):
    """Extraction failure returns error HTML, not a 500 crash."""
    # Make the extractor raise an error
    class BrokenExtractor:
        def extract_from_chunks(self, chunks):
            raise ValueError("LLM returned invalid data")

        def extract_with_gpu_handoff(self, transcript, whisper_service):
            raise ValueError("LLM returned invalid data")

    review_app.state.clinical_extractor = BrokenExtractor()

    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/extract"
    )
    # Should return error HTML, not 500
    assert response.status_code == 200
    assert "error" in response.text.lower()


# --- GET / (index with session list) ---


@pytest.mark.asyncio
async def test_index_includes_session_list(
    review_client, sample_saved_session
):
    """Homepage includes saved sessions in the list."""
    response = await review_client.get("/")
    assert response.status_code == 200
    # Should show session info on the homepage
    assert "session" in response.text.lower()


# --- Patient summary tab and template UI tests ---


@pytest.mark.asyncio
async def test_review_page_has_patient_summary_tab(
    review_client, sample_saved_session, fake_session_store
):
    """Review page has Clinical Note and Patient Summary tab buttons."""
    # Add patient_summary data to the session
    sample_saved_session.patient_summary = {
        "what_we_did": "We fixed a cavity today.",
        "whats_next": "Come back in 6 months.",
        "home_care": "Brush and floss daily.",
    }
    fake_session_store.update_session(sample_saved_session)

    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "Clinical Note" in response.text
    assert "Patient Summary" in response.text
    assert "tab-btn" in response.text


@pytest.mark.asyncio
async def test_review_page_renders_patient_summary_content(
    review_client, sample_saved_session, fake_session_store
):
    """Review page renders patient summary content in the summary tab."""
    sample_saved_session.patient_summary = {
        "what_we_did": "We fixed a cavity on tooth 14.",
        "whats_next": "Return in 6 months for checkup.",
        "home_care": "Brush twice daily, floss once daily.",
    }
    fake_session_store.update_session(sample_saved_session)

    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "We fixed a cavity on tooth 14" in response.text


@pytest.mark.asyncio
async def test_review_page_without_patient_summary(
    review_client, sample_saved_session
):
    """Review page works when patient_summary is None (backward compat)."""
    # sample_saved_session has no patient_summary by default
    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "Patient Summary" in response.text
    assert "not yet generated" in response.text.lower()


@pytest.mark.asyncio
async def test_extract_accepts_template_type(
    review_client, sample_saved_session
):
    """POST /session/{id}/extract accepts optional template_type field."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/extract",
        data={"template_type": "restorative"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_extract_passes_template_type_to_extractor(
    review_client, review_app, sample_saved_session
):
    """Extract route passes template_type to extractor."""
    from tests.conftest import FakeOllamaService, FakeWhisperServiceGpu

    from dental_notes.clinical.extractor import ClinicalExtractor
    from dental_notes.config import Settings

    fake_settings = Settings(
        storage_dir="/tmp/test-transcripts",
        sessions_dir="/tmp/test-sessions",
    )
    fake_ollama = FakeOllamaService()
    fake_extractor = ClinicalExtractor(fake_ollama, fake_settings)
    review_app.state.clinical_extractor = fake_extractor
    review_app.state.whisper_service = FakeWhisperServiceGpu()

    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/extract",
        data={"template_type": "endodontic"},
    )
    assert response.status_code == 200
    # When template_type is provided, extractor should NOT call generate()
    # for auto-detection -- it should use the type directly.
    # So generate_call_count should be 0 (no classification call)
    assert fake_ollama.generate_call_count == 0


@pytest.mark.asyncio
async def test_save_summary_route(
    review_client, sample_saved_session, fake_session_store
):
    """POST /session/{id}/save-summary saves edited patient summary."""
    response = await review_client.post(
        f"/session/{sample_saved_session.session_id}/save-summary",
        data={
            "what_we_did": "Updated: We repaired tooth 14.",
            "whats_next": "Updated: Return in 3 months.",
            "home_care": "Updated: Use sensitivity toothpaste.",
        },
    )
    assert response.status_code == 200

    session = fake_session_store.get_session(sample_saved_session.session_id)
    assert session is not None
    assert session.patient_summary is not None
    assert session.patient_summary["what_we_did"] == "Updated: We repaired tooth 14."


@pytest.mark.asyncio
async def test_print_summary_route(
    review_client, sample_saved_session, fake_session_store
):
    """GET /session/{id}/print-summary returns full HTML page for printing."""
    sample_saved_session.patient_summary = {
        "what_we_did": "We fixed tooth 14.",
        "whats_next": "Return in 6 months.",
        "home_care": "Brush and floss daily.",
    }
    fake_session_store.update_session(sample_saved_session)

    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/print-summary"
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Should be a full HTML page (not a partial)
    assert "<!DOCTYPE html>" in response.text or "<!doctype html>" in response.text.lower()
    assert "We fixed tooth 14" in response.text
    assert "window.print" in response.text


@pytest.mark.asyncio
async def test_parse_transcript_text_handles_assistant(review_client):
    """_parse_transcript_text handles 'Assistant:' speaker labels."""
    from dental_notes.ui.routes import _parse_transcript_text

    text = (
        "Doctor: Crown prep on tooth 14\n\n"
        "Patient: Is that going to hurt?\n\n"
        "Assistant: I'll prepare the anesthetic"
    )
    chunks = _parse_transcript_text(text)
    assert len(chunks) == 3
    speakers = [c[0] for c in chunks]
    assert "Doctor" in speakers
    assert "Patient" in speakers
    assert "Assistant" in speakers


@pytest.mark.asyncio
async def test_review_page_has_template_selector(
    review_client, sample_saved_session, fake_session_store
):
    """Review page has appointment type selector for re-extraction."""
    sample_saved_session.appointment_type = "restorative"
    fake_session_store.update_session(sample_saved_session)

    response = await review_client.get(
        f"/session/{sample_saved_session.session_id}/review"
    )
    assert response.status_code == 200
    assert "appointment_type" in response.text or "template_type" in response.text
