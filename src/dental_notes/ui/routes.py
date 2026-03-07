"""FastAPI routes for session control, SSE streaming, and device listing.

All routes access session_manager via request.app.state -- no global state.
POST routes return HTMX partials for in-place UI updates. The SSE endpoint
streams transcript text and audio level to the browser.
"""

import asyncio
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from dental_notes.session.manager import SessionState

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_session_manager(request: Request):
    """Extract session manager from app state."""
    return request.app.state.session_manager


def _get_templates(request: Request):
    """Extract Jinja2Templates from the main module."""
    from dental_notes.main import templates

    return templates


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main session control page."""
    session_manager = _get_session_manager(request)

    # Get device list (may fail without audio hardware)
    try:
        from dental_notes.audio.capture import list_input_devices

        devices = list_input_devices()
    except Exception:
        devices = []

    return _get_templates(request).TemplateResponse(
        request,
        "index.html",
        {
            "state": session_manager.get_state().value,
            "devices": devices,
            "transcript": session_manager.get_transcript(),
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
        return HTMLResponse(
            content=f'<div id="session-controls" class="error">{e}</div>',
            status_code=409,
        )

    return _get_templates(request).TemplateResponse(
        request,
        "_session.html",
        {"state": session_manager.get_state().value},
    )


@router.post("/session/pause", response_class=HTMLResponse)
async def session_pause(request: Request):
    """Pause the recording session. Returns HTMX partial for session controls."""
    session_manager = _get_session_manager(request)
    try:
        session_manager.pause()
    except RuntimeError as e:
        return HTMLResponse(
            content=f'<div id="session-controls" class="error">{e}</div>',
            status_code=409,
        )

    return _get_templates(request).TemplateResponse(
        request,
        "_session.html",
        {"state": session_manager.get_state().value},
    )


@router.post("/session/resume", response_class=HTMLResponse)
async def session_resume(request: Request):
    """Resume the recording session. Returns HTMX partial for session controls."""
    session_manager = _get_session_manager(request)
    try:
        session_manager.resume()
    except RuntimeError as e:
        return HTMLResponse(
            content=f'<div id="session-controls" class="error">{e}</div>',
            status_code=409,
        )

    return _get_templates(request).TemplateResponse(
        request,
        "_session.html",
        {"state": session_manager.get_state().value},
    )


@router.post("/session/stop", response_class=HTMLResponse)
async def session_stop(request: Request):
    """Stop the recording session. Returns HTMX partial with transcript path."""
    session_manager = _get_session_manager(request)
    try:
        transcript_path = session_manager.stop()
    except RuntimeError as e:
        return HTMLResponse(
            content=f'<div id="session-controls" class="error">{e}</div>',
            status_code=409,
        )

    return _get_templates(request).TemplateResponse(
        request,
        "_session.html",
        {
            "state": session_manager.get_state().value,
            "transcript_path": str(transcript_path),
        },
    )


@router.get("/session/stream")
async def session_stream(request: Request):
    """SSE endpoint streaming transcript updates and audio level."""
    session_manager = _get_session_manager(request)

    async def event_generator():
        last_transcript_len = 0
        was_active = False

        while True:
            if await request.is_disconnected():
                break

            if not session_manager.is_active():
                if was_active:
                    # Session just ended — notify and close
                    yield ServerSentEvent(
                        data="Session ended",
                        event="session_end",
                    )
                    break
                # Not yet active — wait for session to start
                await asyncio.sleep(0.5)
                continue

            was_active = True

            # Get current transcript and send new text
            transcript = session_manager.get_transcript()
            if len(transcript) > last_transcript_len:
                new_text = transcript[last_transcript_len:]
                last_transcript_len = len(transcript)
                yield ServerSentEvent(
                    data=f"<span>{new_text}</span>",
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
            "transcript_length": len(session_manager.get_transcript()),
            "level": round(session_manager.get_level() * 100, 1),
        }
    )
