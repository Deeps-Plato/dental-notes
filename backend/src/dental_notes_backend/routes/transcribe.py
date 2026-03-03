"""POST /transcribe — multipart audio → transcript.

Audio is written to a temp file, transcribed, deleted immediately.
No PHI is retained on the backend.
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from dental_notes_backend.models.api_models import TranscribeResponse
from dental_notes_backend.services import whisper_service

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/transcribe", response_model=TranscribeResponse)
@limiter.limit("10/minute")
async def transcribe(
    request: Request,
    audio_file: UploadFile = File(..., description="WAV or M4A audio, ≤25 MB"),
    language: str = Form(default="en"),
    prompt: str = Form(default=""),
) -> TranscribeResponse:
    if not whisper_service.is_loaded():
        raise HTTPException(status_code=503, detail="Whisper model not loaded yet")

    # Size guard — read up to max+1 bytes to detect oversize without loading it all
    data = await audio_file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds {MAX_AUDIO_BYTES // (1024 * 1024)} MB limit",
        )

    import io

    stream = io.BytesIO(data)
    # Attach filename so whisper_service can infer the suffix
    stream.name = audio_file.filename or "audio.wav"

    try:
        transcript, duration, detected_lang = whisper_service.transcribe(
            stream,
            language=language,
            prompt=prompt or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    logger.info(
        "Transcription complete: %.1fs audio, lang=%s",
        duration,
        detected_lang,
    )

    return TranscribeResponse(
        transcript=transcript,
        duration_seconds=round(duration, 2),
        language=detected_lang,
    )
