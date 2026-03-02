"""FastAPI application factory + lifespan."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from dental_notes_backend.auth import APIKeyMiddleware
from dental_notes_backend.config import settings
from dental_notes_backend.routes.health import router as health_router
from dental_notes_backend.routes.notes import router as notes_router
from dental_notes_backend.routes.transcribe import router as transcribe_router
from dental_notes_backend.services import whisper_service

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load Whisper on startup; release on shutdown."""
    logger.info("Starting dental-notes backend")
    whisper_service.load_model()
    yield
    whisper_service.unload_model()
    logger.info("Backend shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="dental-notes backend",
        description=(
            "Stateless API: transcribes dental audio via Whisper and generates structured "
            "notes via Claude. No PHI is persisted server-side."
        ),
        version="0.1.0",
        lifespan=lifespan,
        # Disable docs in production — enable during dev if needed
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(APIKeyMiddleware)

    app.include_router(health_router)
    app.include_router(transcribe_router)
    app.include_router(notes_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "dental_notes_backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
    )
