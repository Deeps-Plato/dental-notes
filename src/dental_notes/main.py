"""FastAPI application factory with lifespan for Whisper model and session management.

Binds to 127.0.0.1 only (PRV-01). Loads Whisper model at startup for
zero-latency first transcription. Session manager stored on app.state
for route access.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dental_notes.config import Settings
from dental_notes.session.manager import SessionManager
from dental_notes.transcription.whisper_service import WhisperService
from dental_notes.ui.routes import router

logger = logging.getLogger(__name__)

# Resolve paths relative to this file
_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _BASE_DIR / "templates"
_STATIC_DIR = _BASE_DIR / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load Whisper model, create session manager."""
    settings = Settings()
    app.state.settings = settings

    # Load Whisper model (lazy CUDA init at startup)
    whisper_service = WhisperService(settings)
    try:
        whisper_service.load_model()
        logger.info("Whisper model loaded successfully at startup")
    except Exception:
        logger.warning(
            "Whisper model failed to load (expected in headless/test environments). "
            "SessionManager will attempt loading on first session start."
        )

    # Create session manager with injected whisper service
    session_manager = SessionManager(settings)
    if whisper_service.is_loaded:
        session_manager._whisper = whisper_service

    app.state.session_manager = session_manager
    app.state.whisper_service = whisper_service

    # Start hotkey listener (graceful: if pynput fails on headless, web UI still works)
    hotkey_listener = None
    try:
        from dental_notes.ui.hotkey import HotkeyListener

        hotkey_listener = HotkeyListener(session_manager)
        hotkey_listener.start()
    except Exception:
        logger.warning(
            "Hotkey listener failed to start (no X display or pynput unavailable). "
            "Web UI session controls still work."
        )

    yield

    # Shutdown: stop hotkey listener
    if hotkey_listener is not None:
        try:
            hotkey_listener.stop()
        except Exception:
            logger.warning("Failed to stop hotkey listener", exc_info=True)

    # Shutdown: stop any active session, unload model
    if session_manager.is_active():
        try:
            session_manager.stop()
            logger.info("Active session stopped during shutdown")
        except Exception:
            logger.warning("Failed to stop session during shutdown", exc_info=True)

    whisper_service.unload()
    logger.info("Whisper model unloaded, application shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Dental Notes",
        description="Local-first ambient dental note-taking",
        lifespan=lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Include UI routes
    app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "dental_notes.main:app",
        host=settings.host,
        port=settings.port,
    )
