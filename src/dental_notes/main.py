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
from dental_notes.session.store import SessionStore
from dental_notes.transcription.whisper_service import WhisperService
from dental_notes.ui.dictation import router as dictation_router
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

    # Defer Whisper model loading to first session start.
    # Loading at startup blocks the lifespan and delays the web UI.
    whisper_service = WhisperService(settings)
    logger.info(
        "Whisper model will load on first session start "
        "(model=%s, compute=%s)",
        settings.whisper_model,
        settings.compute_type,
    )

    # Create session manager — whisper loads lazily on first start()
    session_manager = SessionManager(settings)

    # Session persistence for review workflow
    session_store = SessionStore(settings.sessions_dir)

    # Clinical extraction pipeline (LLM inference via Ollama)
    try:
        from dental_notes.clinical.extractor import ClinicalExtractor
        from dental_notes.clinical.ollama_service import OllamaService

        ollama_service = OllamaService(
            host=settings.ollama_host,
            model=settings.ollama_model,
        )
        clinical_extractor = ClinicalExtractor(ollama_service, settings)
    except Exception:
        logger.warning(
            "Clinical extractor not available (Ollama or dependencies missing). "
            "Extraction will fail at runtime."
        )
        ollama_service = None
        clinical_extractor = None

    app.state.session_manager = session_manager
    app.state.whisper_service = whisper_service
    app.state.session_store = session_store
    app.state.clinical_extractor = clinical_extractor

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
    app.include_router(dictation_router)

    return app


app = create_app()

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "dental_notes.main:app",
        host=settings.host,
        port=settings.port,
    )
