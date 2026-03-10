"""FastAPI routes for session control, SSE streaming, review, and device listing.

All routes access session_manager via request.app.state -- no global state.
POST routes return HTMX partials for in-place UI updates. The SSE endpoint
streams transcript text and audio level to the browser.

Review routes (review, extract, save, finalize, sessions, note-text) handle
the post-recording workflow: review transcript alongside SOAP note, edit,
copy to clipboard, and finalize (delete transcript).
"""

import asyncio
import html
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_session_manager(request: Request):
    """Extract session manager from app state."""
    return request.app.state.session_manager


def _get_templates(request: Request):
    """Extract Jinja2Templates from the main module."""
    from dental_notes.main import templates

    return templates


def _get_session_store(request: Request):
    """Extract SessionStore from app state."""
    return request.app.state.session_store


def _get_extractor(request: Request):
    """Extract ClinicalExtractor from app state."""
    return request.app.state.clinical_extractor


def _render_session_response(
    request: Request,
    state: str,
    status_code: int = 200,
    **extra_context,
) -> HTMLResponse:
    """Render session controls + OOB transcript area swap.

    Returns the _session.html partial followed by an out-of-band swap
    of #transcript-area so the SSE connection is properly created/destroyed.
    """
    templates = _get_templates(request)
    ctx = {"state": state, **extra_context}

    controls_html = templates.get_template("_session.html").render(ctx)
    transcript_html = templates.get_template("_transcript_oob.html").render(ctx)

    return HTMLResponse(
        content=controls_html + transcript_html,
        status_code=status_code,
    )


def _format_transcript_text(chunks: list[tuple[str, str]]) -> str:
    """Format chunks as labeled transcript text for display."""
    return "\n\n".join(f"{speaker}: {text}" for speaker, text in chunks)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main session control page with session list."""
    session_manager = _get_session_manager(request)

    # Get device list (may fail without audio hardware)
    try:
        from dental_notes.audio.capture import list_input_devices

        devices = list_input_devices()
    except Exception:
        devices = []

    # Get saved sessions for the session list
    try:
        session_store = _get_session_store(request)
        sessions = session_store.list_sessions()
    except Exception:
        sessions = []

    return _get_templates(request).TemplateResponse(
        request,
        "index.html",
        {
            "state": session_manager.get_state().value,
            "devices": devices,
            "chunks": session_manager.get_chunks(),
            "sessions": sessions,
        },
    )


@router.get("/devices")
async def devices():
    """Return JSON list of available input devices."""
    try:
        from dental_notes.audio.capture import list_input_devices

        device_list = list_input_devices()
    except Exception:
        device_list = []

    return JSONResponse(
        content=[{"index": d["index"], "name": d["name"]} for d in device_list]
    )


@router.post("/session/start", response_class=HTMLResponse)
async def session_start(
    request: Request,
    device: int | None = Form(default=None),
):
    """Start a recording session. Returns HTMX partial for session controls."""
    session_manager = _get_session_manager(request)
    try:
        session_manager.start(mic_device=device)
    except RuntimeError as e:
        return _render_session_response(
            request, "idle", status_code=409, error=str(e),
        )
    except Exception as e:
        logger.exception("Failed to start session")
        return _render_session_response(
            request, "idle", status_code=500,
            error=f"Could not start recording: {e}",
        )

    return _render_session_response(
        request, session_manager.get_state().value,
    )


@router.post("/session/pause", response_class=HTMLResponse)
async def session_pause(request: Request):
    """Pause the recording session. Returns HTMX partial for session controls."""
    session_manager = _get_session_manager(request)
    try:
        session_manager.pause()
    except RuntimeError as e:
        return _render_session_response(
            request, session_manager.get_state().value,
            status_code=409, error=str(e),
        )
    except Exception as e:
        logger.exception("Failed to pause session")
        return _render_session_response(
            request, session_manager.get_state().value, error=str(e),
        )

    return _render_session_response(
        request, session_manager.get_state().value,
    )


@router.post("/session/resume", response_class=HTMLResponse)
async def session_resume(request: Request):
    """Resume the recording session. Returns HTMX partial for session controls."""
    session_manager = _get_session_manager(request)
    try:
        session_manager.resume()
    except RuntimeError as e:
        return _render_session_response(
            request, session_manager.get_state().value,
            status_code=409, error=str(e),
        )
    except Exception as e:
        logger.exception("Failed to resume session")
        return _render_session_response(
            request, session_manager.get_state().value, error=str(e),
        )

    return _render_session_response(
        request, session_manager.get_state().value,
    )


@router.post("/session/stop", response_class=HTMLResponse)
async def session_stop(request: Request):
    """Stop recording, create session, auto-extract SOAP note, redirect to review.

    After stopping the session manager, creates a SavedSession via SessionStore,
    runs extraction in the thread pool (to avoid blocking asyncio), and redirects
    to the review page via HX-Redirect header.

    If extraction fails, the session is still saved (status RECORDED) and the
    user is redirected to review where they can retry extraction.
    """
    session_manager = _get_session_manager(request)
    try:
        transcript_path = session_manager.stop()
    except RuntimeError as e:
        return _render_session_response(
            request, session_manager.get_state().value,
            status_code=409, error=str(e),
        )
    except Exception as e:
        logger.exception("Failed to stop session")
        return _render_session_response(
            request, session_manager.get_state().value, error=str(e),
        )

    chunks = session_manager.get_chunks()
    session_store = _get_session_store(request)
    session = session_store.create_session(
        chunks=chunks,
        transcript_path=str(transcript_path),
    )

    # Auto-extract SOAP note in thread pool (blocking LLM call)
    try:
        extractor = _get_extractor(request)
        whisper_service = request.app.state.whisper_service
        transcript_text = _format_transcript_text(chunks)

        loop = asyncio.get_event_loop()
        extraction_result = await loop.run_in_executor(
            None,
            lambda: extractor.extract_with_gpu_handoff(
                transcript_text, whisper_service
            ),
        )

        from dental_notes.session.store import SessionStatus

        session.extraction_result = extraction_result
        session.status = SessionStatus.EXTRACTED
        session_store.update_session(session)
    except Exception:
        logger.exception(
            "Auto-extraction failed for session %s; session saved as RECORDED",
            session.session_id,
        )

    # Return HX-Redirect to review page
    return HTMLResponse(
        content="",
        status_code=200,
        headers={"HX-Redirect": f"/session/{session.session_id}/review"},
    )


@router.get("/session/stream")
async def session_stream(request: Request):
    """SSE endpoint streaming transcript updates and audio level."""
    session_manager = _get_session_manager(request)

    async def event_generator():
        last_chunk_count = 0
        was_active = False

        while True:
            if await request.is_disconnected():
                break

            if not session_manager.is_active():
                if was_active:
                    yield ServerSentEvent(
                        data="Session ended",
                        event="session_end",
                    )
                    break
                await asyncio.sleep(0.5)
                continue

            was_active = True

            # Send new chunks as structured HTML
            new_chunks = session_manager.get_chunks(last_chunk_count)
            if new_chunks:
                last_chunk_count += len(new_chunks)
                html_parts = []
                for speaker, text in new_chunks:
                    safe_text = html.escape(text)
                    html_parts.append(
                        f'<div class="chunk">'
                        f"<strong>{speaker}:</strong> {safe_text}"
                        f"</div>"
                    )
                yield ServerSentEvent(
                    data="".join(html_parts),
                    event="transcript",
                )

            # Send audio level
            level = session_manager.get_level()
            yield ServerSentEvent(
                data=str(round(level * 100, 1)),
                event="level",
            )

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@router.get("/session/status")
async def session_status(request: Request):
    """JSON status endpoint for polling fallback."""
    session_manager = _get_session_manager(request)
    return JSONResponse(
        content={
            "state": session_manager.get_state().value,
            "chunk_count": session_manager.get_chunk_count(),
            "level": round(session_manager.get_level() * 100, 1),
        }
    )


# --- Review workflow routes ---


@router.get("/session/{session_id}/review", response_class=HTMLResponse)
async def session_review(request: Request, session_id: str):
    """Render the review page with transcript and SOAP note side by side."""
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    # Build transcript text from chunks
    transcript_text = _format_transcript_text(session.chunks)

    # Get SOAP note data: prefer edited_note, fall back to extraction_result
    soap_note = None
    if session.extraction_result is not None:
        soap_note = session.extraction_result.soap_note

    return _get_templates(request).TemplateResponse(
        request,
        "review.html",
        {
            "session_id": session_id,
            "session": session,
            "transcript_text": transcript_text,
            "soap_note": soap_note,
            "edited_note": session.edited_note,
        },
    )


@router.post("/session/{session_id}/extract", response_class=HTMLResponse)
async def session_extract(request: Request, session_id: str):
    """Re-extract SOAP note from current transcript.

    Runs extraction in thread pool to avoid blocking the asyncio event loop.
    Uses extract_with_gpu_handoff() for GPU memory management.
    Returns the _review_note.html partial for HTMX swap.
    """
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    try:
        extractor = _get_extractor(request)
        whisper_service = request.app.state.whisper_service
        transcript_text = _format_transcript_text(session.chunks)

        loop = asyncio.get_event_loop()
        extraction_result = await loop.run_in_executor(
            None,
            lambda: extractor.extract_with_gpu_handoff(
                transcript_text, whisper_service
            ),
        )

        from dental_notes.session.store import SessionStatus

        session.extraction_result = extraction_result
        session.edited_note = None
        session.transcript_dirty = False
        session.status = SessionStatus.EXTRACTED
        session_store.update_session(session)

        soap_note = extraction_result.soap_note
    except Exception as e:
        logger.exception("Extraction failed for session %s", session_id)
        error_html = (
            '<div class="error-banner">'
            f"Extraction failed: {html.escape(str(e))}"
            "</div>"
        )
        return HTMLResponse(content=error_html, status_code=200)

    templates = _get_templates(request)
    note_html = templates.get_template("_review_note.html").render(
        {
            "soap_note": soap_note,
            "edited_note": None,
            "session_id": session_id,
        }
    )
    return HTMLResponse(content=note_html, status_code=200)


@router.post("/session/{session_id}/save", response_class=HTMLResponse)
async def session_save(
    request: Request,
    session_id: str,
    subjective: str = Form(default=""),
    objective: str = Form(default=""),
    assessment: str = Form(default=""),
    plan: str = Form(default=""),
    cdt_codes: str = Form(default=""),
    clinical_discussion: str = Form(default=""),
    medications: str = Form(default=""),
    transcript: str = Form(default=""),
):
    """Save edited note fields and updated transcript to session."""
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    # Store edited note as dict
    session.edited_note = {
        "subjective": subjective,
        "objective": objective,
        "assessment": assessment,
        "plan": plan,
        "cdt_codes": cdt_codes,
        "clinical_discussion": clinical_discussion,
        "medications": medications,
    }

    # Update transcript if changed
    if transcript.strip():
        # Parse transcript text back to chunks (best effort)
        new_chunks = _parse_transcript_text(transcript)
        if new_chunks:
            session.chunks = new_chunks

    from dental_notes.session.store import SessionStatus

    session.status = SessionStatus.REVIEWED
    session_store.update_session(session)

    return HTMLResponse(
        content=(
            '<div class="save-confirmation">'
            "Note saved successfully."
            "</div>"
        ),
        status_code=200,
    )


@router.post("/session/{session_id}/finalize", response_class=HTMLResponse)
async def session_finalize(request: Request, session_id: str):
    """Finalize session: delete transcript file and session data.

    Returns confirmation HTML with links to start a new session
    or view the session list.
    """
    session_store = _get_session_store(request)
    session_store.finalize_session(session_id)

    return HTMLResponse(
        content=(
            '<div class="finalize-confirmation">'
            "<h2>Session Finalized</h2>"
            "<p>Transcript has been permanently deleted.</p>"
            '<div class="finalize-actions">'
            '<a href="/" class="btn btn-start">New Session</a>'
            '<a href="/sessions" class="btn btn-resume">Session List</a>'
            "</div>"
            "</div>"
        ),
        status_code=200,
    )


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request):
    """Render the session list page showing all saved sessions."""
    session_store = _get_session_store(request)
    sessions = session_store.list_sessions()

    return _get_templates(request).TemplateResponse(
        request,
        "sessions.html",
        {
            "sessions": sessions,
        },
    )


@router.get("/api/session/{session_id}/note-text")
async def session_note_text(request: Request, session_id: str):
    """Return formatted note text for clipboard copy (server-side formatting).

    Returns plain text response with section headers, suitable for pasting
    into Dentrix or other EHR systems.
    """
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    from dental_notes.clinical.formatter import format_note_for_clipboard

    soap_note = None
    if session.extraction_result is not None:
        soap_note = session.extraction_result.soap_note

    formatted = format_note_for_clipboard(
        soap_note=soap_note,
        edited_note=session.edited_note,
    )

    return PlainTextResponse(content=formatted, status_code=200)


def _parse_transcript_text(text: str) -> list[tuple[str, str]]:
    """Parse transcript text back into (speaker, text) chunks.

    Handles "Speaker: text" format separated by blank lines.
    Falls back to single chunk with "Doctor" label if parsing fails.
    """
    chunks: list[tuple[str, str]] = []
    paragraphs = text.strip().split("\n\n")

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if ": " in paragraph:
            speaker, _, chunk_text = paragraph.partition(": ")
            speaker = speaker.strip()
            if speaker in ("Doctor", "Patient"):
                chunks.append((speaker, chunk_text.strip()))
                continue
        # Fallback: treat as Doctor speech
        chunks.append(("Doctor", paragraph))

    return chunks
