"""Dictation endpoint for field-level mic-to-text via Whisper.

Accepts raw PCM 16-bit 16kHz mono audio bytes from the browser's
MediaRecorder, converts to float32 numpy array, and transcribes
using WhisperService. Returns JSON with transcribed text.

This is a simplified single-shot transcription for short audio clips
(typically 2-30 seconds of speech). No VAD, no chunking -- the browser
handles recording start/stop.
"""

import logging
import struct

import numpy as np
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# PCM format: 16-bit signed little-endian, 16kHz mono
PCM_SAMPLE_RATE = 16000
PCM_BYTES_PER_SAMPLE = 2  # 16-bit = 2 bytes


def _pcm_bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    """Convert raw PCM 16-bit LE audio bytes to float32 numpy array.

    Args:
        audio_bytes: Raw PCM 16-bit little-endian mono audio at 16kHz.

    Returns:
        Float32 numpy array normalized to [-1.0, 1.0].
    """
    if len(audio_bytes) == 0:
        return np.array([], dtype=np.float32)

    # Ensure even number of bytes (16-bit samples)
    byte_count = len(audio_bytes) - (len(audio_bytes) % PCM_BYTES_PER_SAMPLE)
    if byte_count == 0:
        return np.array([], dtype=np.float32)

    num_samples = byte_count // PCM_BYTES_PER_SAMPLE
    samples = struct.unpack(f"<{num_samples}h", audio_bytes[:byte_count])
    return np.array(samples, dtype=np.float32) / 32768.0


@router.post("/dictate")
async def dictate(request: Request) -> Response:
    """Transcribe a short audio clip for field-level dictation.

    Accepts raw PCM 16-bit 16kHz mono audio in the request body.
    Returns JSON: {"text": "transcribed text"}.

    Returns 503 if Whisper model is not loaded (e.g., GPU busy with
    LLM extraction).
    """
    whisper_service = request.app.state.whisper_service

    # Check if Whisper is available
    if not whisper_service.is_loaded:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Whisper model not available "
                    "(GPU in use for extraction)"
                )
            },
        )

    # Read raw audio bytes from request body
    audio_bytes = await request.body()

    # Handle empty audio
    if len(audio_bytes) == 0:
        return JSONResponse(content={"text": ""})

    # Convert PCM bytes to float32 array
    audio_array = _pcm_bytes_to_float32(audio_bytes)

    if len(audio_array) == 0:
        return JSONResponse(content={"text": ""})

    # Transcribe via Whisper
    try:
        text = whisper_service.transcribe(audio_array)
    except Exception:
        logger.exception("Dictation transcription failed")
        return JSONResponse(
            status_code=500,
            content={"detail": "Transcription failed"},
        )

    return JSONResponse(content={"text": text})
