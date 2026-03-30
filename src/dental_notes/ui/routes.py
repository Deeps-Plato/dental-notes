"""FastAPI routes for session control, SSE streaming, review, and device listing.

All routes access session_manager via request.app.state -- no global state.
POST routes return HTMX partials for in-place UI updates. The SSE endpoint
streams transcript text and audio level to the browser.

Review routes (review, extract, save, finalize, sessions, note-text) handle
the post-recording workflow: review transcript alongside SOAP note, edit,
copy to clipboard, and finalize (delete transcript).

Template/appointment type flows through:
  session_start -> app.state.appointment_type -> SSE hotwords -> session_stop
  -> extraction with template_type -> session storage

Phase 5 additions:
  - /session/next-patient: batch multi-patient transition
  - /api/health: JSON health check endpoint
  - /health-bar: HTMX-polled health status bar partial
  - /sessions: date and status filtering with defaults
  - SSE: auto_paused state, mic_disconnected, transcription_behind, oom_retry
  - /session/{id}/retry-extract: manual extraction retry
  - /session/{id}/extraction-status: extraction state partial
"""

import asyncio
import html
import json
import logging
from datetime import date

from fastapi import APIRouter, Form, Query, Request
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


def _get_health_checker(request: Request):
    """Extract HealthChecker from app state."""
    return request.app.state.health_checker


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

    # Initial health check data for the status bar
    health = None
    try:
        health_checker = _get_health_checker(request)
        loop = asyncio.get_event_loop()
        health = await loop.run_in_executor(
            None, health_checker.check_all
        )
    except Exception:
        pass

    return _get_templates(request).TemplateResponse(
        request,
        "index.html",
        {
            "state": session_manager.get_state().value,
            "devices": devices,
            "chunks": session_manager.get_chunks(),
            "sessions": sessions,
            "health": health,
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
    """Start a recording session. Returns HTMX partial for session controls.

    Auto-detection infers appointment type from transcript during extraction.
    General hotwords used during recording; template applied at review time.
    """
    session_manager = _get_session_manager(request)

    # Default to general — auto-detect determines template during extraction
    request.app.state.appointment_type = "general"

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

    # Read appointment_type from app state (set by session_start)
    appt_type = getattr(request.app.state, "appointment_type", "general")

    session = session_store.create_session(
        chunks=chunks,
        transcript_path=str(transcript_path),
    )
    session.appointment_type = appt_type

    # Determine template_type: pass None for "general" (triggers auto-detect)
    template_type = None if appt_type == "general" else appt_type

    # Auto-extract SOAP note in thread pool (blocking LLM call)
    try:
        extractor = _get_extractor(request)
        whisper_service = request.app.state.whisper_service
        transcript_text = _format_transcript_text(chunks)

        loop = asyncio.get_event_loop()
        extraction_result = await loop.run_in_executor(
            None,
            lambda: extractor.extract_with_gpu_handoff(
                transcript_text, whisper_service, template_type=template_type
            ),
        )

        from dental_notes.session.store import SessionStatus

        session.extraction_result = extraction_result
        session.patient_summary = (
            extraction_result.patient_summary.model_dump()
            if extraction_result.patient_summary
            else None
        )
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


@router.post("/session/next-patient", response_class=HTMLResponse)
async def session_next_patient(request: Request):
    """Save current session and immediately start recording next patient.

    Calls session_manager.next_patient() which stops the current session,
    saves it via SessionStore, and starts a new recording. Does NOT trigger
    extraction (deferred to review for fast transitions).
    """
    session_manager = _get_session_manager(request)
    session_store = _get_session_store(request)
    try:
        session_manager.next_patient(session_store)
    except RuntimeError as e:
        return _render_session_response(
            request, session_manager.get_state().value,
            status_code=409, error=str(e),
        )
    except Exception as e:
        logger.exception("Failed to transition to next patient")
        return _render_session_response(
            request, session_manager.get_state().value,
            status_code=500, error=f"Could not switch patient: {e}",
        )

    return _render_session_response(
        request, session_manager.get_state().value,
    )


@router.get("/session/stream")
async def session_stream(request: Request):
    """SSE endpoint streaming transcript updates and audio level.

    Template-specific hotwords are not used during live recording because
    the appointment type is auto-detected at extraction time, not pre-selected.
    The expanded DENTAL_INITIAL_PROMPT provides general dental vocabulary.
    """
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

            # Send status event with state flags
            status_data = {
                "state": session_manager.get_state().value,
            }
            if session_manager.is_mic_disconnected():
                status_data["mic_disconnected"] = True
            if session_manager.is_transcription_behind():
                status_data["transcription_behind"] = True
            oom_count = session_manager.get_oom_retry_count()
            if oom_count > 0:
                status_data["oom_retry_count"] = oom_count
            yield ServerSentEvent(
                data=json.dumps(status_data),
                event="status",
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
    """Render the review page with transcript, SOAP note, and patient summary."""
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
            "patient_summary": session.patient_summary,
            "appointment_type": session.appointment_type,
        },
    )


@router.post("/session/{session_id}/extract", response_class=HTMLResponse)
async def session_extract(
    request: Request,
    session_id: str,
    template_type: str | None = Form(default=None),
):
    """Re-extract SOAP note from current transcript with optional template type.

    Runs extraction in thread pool to avoid blocking the asyncio event loop.
    Uses extract_with_gpu_handoff() for GPU memory management.
    Returns the _review_note.html partial for HTMX swap, plus an OOB swap
    for the patient summary tab content.
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
                transcript_text, whisper_service,
                template_type=template_type,
            ),
        )

        from dental_notes.session.store import SessionStatus

        session.extraction_result = extraction_result
        session.patient_summary = (
            extraction_result.patient_summary.model_dump()
            if extraction_result.patient_summary
            else None
        )
        session.edited_note = None
        session.transcript_dirty = False
        session.status = SessionStatus.EXTRACTED
        if template_type:
            session.appointment_type = template_type
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
    # OOB swap for patient summary tab content
    summary_html = templates.get_template("_review_summary.html").render(
        {
            "patient_summary": session.patient_summary,
            "session_id": session_id,
        }
    )
    oob_summary = (
        f'<div id="summary-panel" hx-swap-oob="innerHTML">'
        f"{summary_html}</div>"
    )
    return HTMLResponse(
        content=note_html + oob_summary, status_code=200
    )


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
async def sessions_list(
    request: Request,
    date: str | None = Query(default=None, alias="date"),
    status: str | None = Query(default=None, alias="status"),
):
    """Render the session list page with date and status filters.

    Defaults to today's date when no date param is provided.
    Accepts status values matching SessionStatus enum (recorded, extracted, etc.).
    """
    from dental_notes.session.store import SessionStatus

    session_store = _get_session_store(request)

    # Parse date filter (default to today in UTC for consistency
    # with session created_at which uses datetime.now(timezone.utc))
    filter_date = None
    show_all_dates = date == "all"
    if not show_all_dates:
        if date:
            try:
                from datetime import date as date_type

                parts = date.split("-")
                filter_date = date_type(
                    int(parts[0]), int(parts[1]), int(parts[2])
                )
            except (ValueError, IndexError):
                from datetime import datetime as dt_type, timezone as tz

                filter_date = dt_type.now(tz.utc).date()
        else:
            from datetime import datetime as dt_type, timezone as tz

            filter_date = dt_type.now(tz.utc).date()

    # Parse status filter
    filter_status = None
    if status:
        try:
            filter_status = SessionStatus(status)
        except ValueError:
            pass

    sessions = session_store.list_sessions(
        filter_date=filter_date,
        filter_status=filter_status,
    )

    # Count incomplete sessions for banner
    try:
        incomplete_sessions = session_store.scan_incomplete_sessions()
        incomplete_count = len(incomplete_sessions)
    except Exception:
        incomplete_count = 0

    return _get_templates(request).TemplateResponse(
        request,
        "sessions.html",
        {
            "sessions": sessions,
            "filter_date": str(filter_date) if filter_date else "",
            "filter_status": status or "",
            "show_all_dates": show_all_dates,
            "incomplete_count": incomplete_count,
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


@router.post("/session/{session_id}/save-summary", response_class=HTMLResponse)
async def session_save_summary(
    request: Request,
    session_id: str,
    what_we_did: str = Form(default=""),
    whats_next: str = Form(default=""),
    home_care: str = Form(default=""),
):
    """Save edited patient summary fields to session."""
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    session.patient_summary = {
        "what_we_did": what_we_did,
        "whats_next": whats_next,
        "home_care": home_care,
    }
    session_store.update_session(session)

    return HTMLResponse(
        content=(
            '<div class="save-confirmation">'
            "Patient summary saved."
            "</div>"
        ),
        status_code=200,
    )


@router.get(
    "/session/{session_id}/print-summary", response_class=HTMLResponse
)
async def session_print_summary(request: Request, session_id: str):
    """Return full HTML page for printing patient summary.

    This is a standalone page (not a partial) with @media print CSS.
    Opens in a new tab with a Print button that calls window.print().
    """
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    templates = _get_templates(request)
    return templates.TemplateResponse(
        request,
        "_print_summary.html",
        {
            "session_id": session_id,
            "patient_summary": session.patient_summary,
            "created_at": session.created_at,
        },
    )


# --- Health monitoring routes ---


@router.get("/api/health")
async def health_check(request: Request):
    """Return JSON health status of all system components.

    Runs HealthChecker.check_all() in a thread executor to avoid blocking
    the asyncio event loop (Ollama check makes HTTP call).
    """
    health_checker = _get_health_checker(request)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, health_checker.check_all)
    return JSONResponse(content=result)


@router.get("/health-bar", response_class=HTMLResponse)
async def health_bar(request: Request):
    """Return _health_bar.html partial with component health indicators.

    HTMX polls this endpoint every 30 seconds for status updates.
    """
    health_checker = _get_health_checker(request)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, health_checker.check_all)

    templates = _get_templates(request)
    return HTMLResponse(
        content=templates.get_template("_health_bar.html").render(
            {"health": result}
        ),
    )


# --- Extraction retry routes ---


@router.post(
    "/session/{session_id}/retry-extract", response_class=HTMLResponse
)
async def session_retry_extract(request: Request, session_id: str):
    """Trigger extraction retry for a session where extraction failed.

    Uses create_retry_extract wrapper for transient error resilience.
    Returns _extraction_status.html partial with result or error.
    """
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    try:
        from dental_notes.clinical.extractor import create_retry_extract

        extractor = _get_extractor(request)
        settings = request.app.state.settings
        whisper_service = request.app.state.whisper_service

        retry_fn = create_retry_extract(extractor, settings)
        transcript_text = _format_transcript_text(session.chunks)

        loop = asyncio.get_event_loop()
        extraction_result = await loop.run_in_executor(
            None,
            lambda: retry_fn(transcript_text, whisper_service),
        )

        from dental_notes.session.store import SessionStatus

        session.extraction_result = extraction_result
        session.patient_summary = (
            extraction_result.patient_summary.model_dump()
            if extraction_result.patient_summary
            else None
        )
        session.status = SessionStatus.EXTRACTED
        session_store.update_session(session)

        templates = _get_templates(request)
        return HTMLResponse(
            content=templates.get_template(
                "_extraction_status.html"
            ).render(
                {
                    "extraction_state": "success",
                    "session_id": session_id,
                }
            ),
        )
    except Exception as e:
        logger.exception(
            "Extraction retry failed for session %s", session_id
        )
        templates = _get_templates(request)
        return HTMLResponse(
            content=templates.get_template(
                "_extraction_status.html"
            ).render(
                {
                    "extraction_state": "failed",
                    "session_id": session_id,
                    "error": str(e),
                }
            ),
        )


@router.get(
    "/session/{session_id}/extraction-status",
    response_class=HTMLResponse,
)
async def session_extraction_status(request: Request, session_id: str):
    """Return _extraction_status.html partial with current extraction state.

    States: idle (not yet extracted), extracted (success), failed (show retry).
    """
    session_store = _get_session_store(request)
    session = session_store.get_session(session_id)

    if session is None:
        return HTMLResponse(
            content="<h1>Session not found</h1>",
            status_code=404,
        )

    from dental_notes.session.store import SessionStatus

    if session.status == SessionStatus.EXTRACTED:
        extraction_state = "success"
    elif session.status == SessionStatus.REVIEWED:
        extraction_state = "success"
    else:
        extraction_state = "idle"

    templates = _get_templates(request)
    return HTMLResponse(
        content=templates.get_template("_extraction_status.html").render(
            {
                "extraction_state": extraction_state,
                "session_id": session_id,
            }
        ),
    )


def _parse_transcript_text(text: str) -> list[tuple[str, str]]:
    """Parse transcript text back into (speaker, text) chunks.

    Handles "Speaker: text" format separated by blank lines.
    Supports 3-way speaker labels: Doctor, Patient, Assistant.
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
            if speaker in ("Doctor", "Patient", "Assistant"):
                chunks.append((speaker, chunk_text.strip()))
                continue
        # Fallback: treat as Doctor speech
        chunks.append(("Doctor", paragraph))

    return chunks
