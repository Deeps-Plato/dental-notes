"""Singleton WhisperModel wrapper.

The model is loaded once on startup (via lifespan) and shared across requests.
Audio files are written to a NamedTemporaryFile, transcribed, then **deleted
immediately** — no PHI is retained on the backend filesystem.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from faster_whisper import WhisperModel

from dental_notes_backend.config import settings

logger = logging.getLogger(__name__)

# Dental vocabulary hint fed to Whisper as an initial prompt.
DENTAL_PROMPT = (
    "Dental clinical note. Terms: probing depth, bleeding on probing, BOP, furcation, "
    "mobility, recession, gingival margin, CEJ, calculus, plaque, composite, amalgam, "
    "crown, implant, extraction, root canal, pulpitis, periapical, caries, D2391, "
    "periodontal, gingivitis, periodontitis, AAP stage, grade, occlusion, malocclusion, "
    "TMJ, bruxism, fluoride, sealant, prophylaxis, scaling, root planing, SRP."
)

_model: WhisperModel | None = None


def load_model() -> None:
    """Load the Whisper model into memory.  Called once from FastAPI lifespan."""
    global _model
    logger.info(
        "Loading Whisper model=%s device=%s compute=%s",
        settings.whisper_model_size,
        settings.whisper_device,
        settings.whisper_compute_type,
    )
    _model = WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    logger.info("Whisper model loaded.")


def unload_model() -> None:
    """Release the model (called on shutdown)."""
    global _model
    _model = None
    logger.info("Whisper model unloaded.")


def is_loaded() -> bool:
    return _model is not None


def transcribe(
    audio: BinaryIO,
    language: str = "en",
    prompt: str | None = None,
) -> tuple[str, float, str]:
    """Transcribe *audio* and return (transcript, duration_seconds, language).

    The audio bytes are written to a temporary file, transcribed, then the
    temporary file is deleted.  The caller's BinaryIO object is not modified.
    """
    if _model is None:
        raise RuntimeError("WhisperModel not loaded — call load_model() first.")

    suffix = _infer_suffix(audio)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(audio.read())

    try:
        combined_prompt = f"{DENTAL_PROMPT} {prompt or ''}".strip()
        segments, info = _model.transcribe(
            tmp_path,
            language=language if language != "auto" else None,
            initial_prompt=combined_prompt,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        duration = float(info.duration)
        detected = info.language or language
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            logger.warning("Could not delete temp audio file: %s", tmp_path)

    return text, duration, detected


def _infer_suffix(audio: BinaryIO) -> str:
    """Return a file extension hint from the stream name, defaulting to .wav."""
    name = getattr(audio, "name", "") or getattr(audio, "filename", "") or ""
    ext = Path(name).suffix.lower()
    return ext if ext in {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"} else ".wav"
