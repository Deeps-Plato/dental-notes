"""Tests for WhisperService with dental vocabulary prompt.

Uses a FakeWhisperModel to avoid importing real faster_whisper
(no GPU needed in tests).
"""

from collections import namedtuple
from pathlib import Path

import numpy as np
import pytest

from dental_notes.config import Settings

FakeSegment = namedtuple("FakeSegment", ["text"])


class FakeWhisperModel:
    """Records initialization args and returns fake segments from transcribe()."""

    def __init__(self, model_size: str, **kwargs):
        self.model_size = model_size
        self.init_kwargs = kwargs

    def transcribe(self, audio, **kwargs):
        """Return fake segments and info. Records kwargs for assertion."""
        self.last_transcribe_kwargs = kwargs
        segments = [FakeSegment(text=" hello "), FakeSegment(text=" world ")]
        info = None  # Not used in our service
        return segments, info


@pytest.fixture
def settings():
    return Settings(whisper_model="small", compute_type="int8")


class TestWhisperServiceLazyLoading:
    """WhisperService does not load the model on init."""

    def test_model_lazy_loading(self, settings):
        from dental_notes.transcription.whisper_service import WhisperService

        service = WhisperService(settings)
        assert service.is_loaded is False

    def test_unload(self, settings):
        from dental_notes.transcription.whisper_service import WhisperService

        service = WhisperService(settings)
        # Simulate a loaded model
        service._model = FakeWhisperModel("small")
        assert service.is_loaded is True

        service.unload()
        assert service.is_loaded is False


class TestWhisperServiceModelLoading:
    """load_model() creates WhisperModel with correct parameters."""

    def test_load_model_params(self, settings):
        import sys
        import types

        from dental_notes.transcription.whisper_service import WhisperService

        service = WhisperService(settings)

        # Create a fake faster_whisper module so the import inside load_model() resolves
        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel  # type: ignore[attr-defined]
        sys.modules["faster_whisper"] = fake_module
        try:
            service.load_model()
        finally:
            del sys.modules["faster_whisper"]

        assert service.is_loaded is True
        assert service._model.model_size == "small"
        assert service._model.init_kwargs["device"] == "cuda"
        assert service._model.init_kwargs["compute_type"] == "int8"


class TestWhisperServiceTranscription:
    """transcribe() calls model with correct parameters and returns text."""

    def _make_service_with_fake(self, settings):
        from dental_notes.transcription.whisper_service import WhisperService

        service = WhisperService(settings)
        service._model = FakeWhisperModel("small")
        return service

    def test_dental_prompt(self, settings):
        from dental_notes.transcription.whisper_service import (
            DENTAL_INITIAL_PROMPT,
        )

        service = self._make_service_with_fake(settings)
        audio = np.zeros(16000, dtype=np.float32)
        service.transcribe(audio)

        # Verify prompt was passed to transcribe (uses _initial_prompt which
        # equals DENTAL_INITIAL_PROMPT when no custom vocab file exists)
        assert (
            service._model.last_transcribe_kwargs["initial_prompt"]
            == DENTAL_INITIAL_PROMPT
        )

        # Verify prompt contains required vocabulary categories
        assert "teeth" in DENTAL_INITIAL_PROMPT.lower()
        assert "MOD" in DENTAL_INITIAL_PROMPT
        assert "composite" in DENTAL_INITIAL_PROMPT.lower()
        assert "SRP" in DENTAL_INITIAL_PROMPT
        assert "Shofu" in DENTAL_INITIAL_PROMPT
        assert "Lidocaine" in DENTAL_INITIAL_PROMPT
        assert "Herculite" in DENTAL_INITIAL_PROMPT
        assert "radiolucency" in DENTAL_INITIAL_PROMPT
        assert "CEJ" in DENTAL_INITIAL_PROMPT

    def test_transcribe_returns_text(self, settings):
        service = self._make_service_with_fake(settings)
        audio = np.zeros(16000, dtype=np.float32)
        result = service.transcribe(audio)

        # FakeWhisperModel returns " hello " and " world "
        assert result == "hello world"

    def test_transcribe_safety_params(self, settings):
        service = self._make_service_with_fake(settings)
        audio = np.zeros(16000, dtype=np.float32)
        service.transcribe(audio)

        kwargs = service._model.last_transcribe_kwargs
        assert kwargs["vad_filter"] is True
        assert kwargs["no_speech_threshold"] == 0.6

    def test_transcribe_passes_language(self, settings):
        service = self._make_service_with_fake(settings)
        audio = np.zeros(16000, dtype=np.float32)
        service.transcribe(audio)

        kwargs = service._model.last_transcribe_kwargs
        assert kwargs["language"] == "en"

    def test_transcribe_accepts_hotwords_parameter(self, settings):
        """transcribe() forwards hotwords to model.transcribe() when provided."""
        service = self._make_service_with_fake(settings)
        audio = np.zeros(16000, dtype=np.float32)
        service.transcribe(audio, hotwords="Lidocaine Septocaine")

        kwargs = service._model.last_transcribe_kwargs
        assert kwargs["hotwords"] == "Lidocaine Septocaine"

    def test_transcribe_without_hotwords_backward_compatible(self, settings):
        """transcribe() works without hotwords parameter (no hotwords key)."""
        service = self._make_service_with_fake(settings)
        audio = np.zeros(16000, dtype=np.float32)
        service.transcribe(audio)

        kwargs = service._model.last_transcribe_kwargs
        assert "hotwords" not in kwargs


class TestSettingsCustomVocabPath:
    """Settings has custom_vocab_path field."""

    def test_custom_vocab_path_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.custom_vocab_path == Path("vocab.txt")
