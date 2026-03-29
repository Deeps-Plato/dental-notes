"""Whisper transcription service with dental vocabulary prompting.

Wraps faster-whisper's WhisperModel with lazy loading, int8 compute type
for GTX 1050 compatibility, and a comprehensive dental initial_prompt that
helps Whisper accurately transcribe clinical terminology.

CRITICAL: Uses compute_type="int8" -- GTX 1050 (CC 6.1) does NOT support
float16 in CTranslate2. Using float16 will either fail or silently fall
back to float32 (slower, more VRAM).
"""

import logging

import numpy as np

from dental_notes.config import Settings
from dental_notes.transcription.vocab import (
    DENTAL_INITIAL_PROMPT,
    build_initial_prompt,
)

logger = logging.getLogger(__name__)


class WhisperService:
    """Wrapper around faster-whisper WhisperModel with dental vocabulary.

    The model is NOT loaded on init (lazy loading). Call load_model() before
    transcribe(). This avoids import-time CUDA dependency and allows tests
    to run without a GPU.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._initial_prompt = build_initial_prompt(
            settings.custom_vocab_path,
        )

    def load_model(self) -> None:
        """Load the Whisper model onto GPU.

        Imports faster_whisper inside this method to avoid import-time
        CUDA dependency. Uses int8 compute type for CC 6.1 GPU compatibility.
        """
        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper model: %s (compute_type=%s)",
            self._settings.whisper_model,
            self._settings.compute_type,
        )
        self._model = WhisperModel(
            self._settings.whisper_model,
            device="cuda",
            compute_type=self._settings.compute_type,
        )
        logger.info("Whisper model loaded successfully")

    def transcribe(
        self,
        audio: np.ndarray,
        hotwords: str | None = None,
    ) -> str:
        """Transcribe an audio chunk using Whisper with dental vocabulary.

        Args:
            audio: Float32 numpy array of audio samples at 16kHz.
            hotwords: Optional space-separated hotwords string for
                procedure-specific term boosting.

        Returns:
            Transcribed text with segments concatenated and stripped.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        kwargs: dict = {
            "initial_prompt": self._initial_prompt,
            "vad_filter": True,
            "no_speech_threshold": 0.6,
            "language": "en",
        }
        if hotwords is not None:
            kwargs["hotwords"] = hotwords

        segments, _ = self._model.transcribe(audio, **kwargs)

        # Iterate segments, join text with spaces, strip whitespace
        text_parts = [segment.text for segment in segments]
        return " ".join(part.strip() for part in text_parts if part.strip())

    @property
    def is_loaded(self) -> bool:
        """Return True if the Whisper model is loaded."""
        return self._model is not None

    def unload(self) -> None:
        """Release the model and VRAM."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Whisper model unloaded")
