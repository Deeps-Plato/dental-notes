"""GET /health — liveness check."""

from fastapi import APIRouter

from dental_notes_backend.config import settings
from dental_notes_backend.services import whisper_service

router = APIRouter()


@router.get("/health")
def health() -> dict:  # type: ignore[type-arg]
    return {
        "status": "ok",
        "whisper_loaded": whisper_service.is_loaded(),
        "model_size": settings.whisper_model_size,
    }
