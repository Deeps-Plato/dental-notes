"""FastAPI application factory + lifespan."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from dental_notes_backend.auth import APIKeyMiddleware
from dental_notes_backend.config import settings
from dental_notes_backend.routes.health import router as health_router
from dental_notes_backend.routes.notes import router as notes_router
from dental_notes_backend.routes.transcribe import router as transcribe_router
from dental_notes_backend.services import whisper_service

# ── Structured JSON logging ──────────────────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """Emit structured JSON logs with PHI-safe fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        return json.dumps(entry)


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers = [handler]


_setup_logging()
logger = logging.getLogger(__name__)


# ── Rate limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        {"detail": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
    )


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load Whisper on startup; release on shutdown."""
    logger.info("Starting dental-notes backend")
    whisper_service.load_model()
    yield
    whisper_service.unload_model()
    logger.info("Backend shutdown complete")


# ── App factory ──────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title="dental-notes backend",
        description=(
            "Stateless API: transcribes dental audio via Whisper and generates structured "
            "notes via Claude. No PHI is persisted server-side."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded)  # type: ignore[arg-type]

    # Auth
    app.add_middleware(APIKeyMiddleware)

    # Routes
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
