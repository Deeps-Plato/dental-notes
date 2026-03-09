"""Tests for ClinicalExtractor -- transcript to SOAP note with CDT codes.

Covers extract(), extract_from_chunks(), extract_with_gpu_handoff(),
and error handling. Uses FakeOllamaService and FakeWhisperServiceGpu
from conftest.py -- no real Ollama or GPU needed.
"""

import json
import re

import pytest

from dental_notes.clinical.extractor import ClinicalExtractor
from dental_notes.clinical.models import ExtractionResult
from dental_notes.config import Settings
from tests.conftest import (
    FakeOllamaService,
    FakeWhisperServiceGpu,
    SAMPLE_DENTAL_TRANSCRIPT,
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Settings for extraction tests."""
    return Settings(
        storage_dir=tmp_path / "transcripts",
        ollama_temperature=0.1,
        ollama_num_ctx=4096,
    )


@pytest.fixture
def extractor(fake_ollama_service: FakeOllamaService, settings: Settings):
    """ClinicalExtractor with FakeOllamaService."""
    return ClinicalExtractor(fake_ollama_service, settings)


# --- extract() tests ---


class TestExtract:
    """Tests for ClinicalExtractor.extract()."""

    def test_extract_returns_extraction_result(
        self, extractor: ClinicalExtractor, sample_transcript: str
    ) -> None:
        """extract() returns an ExtractionResult instance."""
        result = extractor.extract(sample_transcript)
        assert isinstance(result, ExtractionResult)

    def test_extract_soap_note_has_four_sections(
        self, extractor: ClinicalExtractor, sample_transcript: str
    ) -> None:
        """SOAP note has non-empty subjective, objective, assessment, plan."""
        result = extractor.extract(sample_transcript)
        note = result.soap_note
        assert note.subjective
        assert note.objective
        assert note.assessment
        assert note.plan

    def test_extract_cdt_codes_present(
        self, extractor: ClinicalExtractor, sample_transcript: str
    ) -> None:
        """CDT codes list is non-empty."""
        result = extractor.extract(sample_transcript)
        assert len(result.soap_note.cdt_codes) > 0

    def test_extract_cdt_codes_valid_format(
        self, extractor: ClinicalExtractor, sample_transcript: str
    ) -> None:
        """Each CDT code matches D followed by 4 digits."""
        result = extractor.extract(sample_transcript)
        for cdt in result.soap_note.cdt_codes:
            assert re.match(r"^D\d{4}$", cdt.code), (
                f"Invalid CDT code format: {cdt.code}"
            )

    def test_extract_clinical_summary_present(
        self, extractor: ClinicalExtractor, sample_transcript: str
    ) -> None:
        """clinical_summary is a non-empty string."""
        result = extractor.extract(sample_transcript)
        assert isinstance(result.clinical_summary, str)
        assert len(result.clinical_summary) > 0

    def test_extract_passes_system_prompt(
        self,
        extractor: ClinicalExtractor,
        fake_ollama_service: FakeOllamaService,
        sample_transcript: str,
    ) -> None:
        """System prompt sent to LLM contains SOAP and CDT references."""
        extractor.extract(sample_transcript)
        prompt = fake_ollama_service.last_system_prompt
        assert prompt is not None
        assert "SOAP" in prompt
        assert "CDT" in prompt

    def test_extract_passes_transcript_as_user_content(
        self,
        extractor: ClinicalExtractor,
        fake_ollama_service: FakeOllamaService,
        sample_transcript: str,
    ) -> None:
        """Transcript text is passed as user_content to LLM."""
        extractor.extract(sample_transcript)
        content = fake_ollama_service.last_user_content
        assert content is not None
        assert "sensitive to cold" in content

    def test_extract_invalid_json_raises_value_error(
        self, settings: Settings
    ) -> None:
        """Invalid JSON from LLM raises ValueError."""
        bad_ollama = FakeOllamaService(response_data={"not": "valid"})
        # Override generate_structured to return non-schema JSON
        bad_ollama.generate_structured = (
            lambda system_prompt, user_content, schema, **kw: "not json at all"
        )
        ext = ClinicalExtractor(bad_ollama, settings)
        with pytest.raises(ValueError, match="LLM returned invalid"):
            ext.extract("some transcript")

    def test_extract_uses_settings_temperature(
        self, settings: Settings, sample_transcript: str
    ) -> None:
        """Temperature from settings is passed to generate_structured."""
        captured_kwargs: dict = {}

        class TrackingOllama(FakeOllamaService):
            def generate_structured(
                self, system_prompt, user_content, schema, **kwargs
            ):
                captured_kwargs.update(kwargs)
                return super().generate_structured(
                    system_prompt, user_content, schema, **kwargs
                )

        tracking = TrackingOllama()
        ext = ClinicalExtractor(tracking, settings)
        ext.extract(sample_transcript)
        assert captured_kwargs.get("temperature") == 0.1
        assert captured_kwargs.get("num_ctx") == 4096


# --- extract_from_chunks() tests ---


class TestExtractFromChunks:
    """Tests for ClinicalExtractor.extract_from_chunks()."""

    def test_extract_from_chunks_formats_correctly(
        self,
        extractor: ClinicalExtractor,
        fake_ollama_service: FakeOllamaService,
    ) -> None:
        """Chunks are formatted as 'Speaker: text' lines joined by double newlines."""
        chunks = [
            ("Doctor", "Open wide please."),
            ("Patient", "It hurts on the right side."),
        ]
        extractor.extract_from_chunks(chunks)
        content = fake_ollama_service.last_user_content
        assert content is not None
        assert "Doctor: Open wide please." in content
        assert "Patient: It hurts on the right side." in content
        # Double newline separation
        assert "\n\n" in content

    def test_extract_from_chunks_returns_result(
        self, extractor: ClinicalExtractor
    ) -> None:
        """extract_from_chunks returns ExtractionResult."""
        chunks = [
            ("Doctor", "Let me check tooth 14."),
            ("Patient", "Okay."),
        ]
        result = extractor.extract_from_chunks(chunks)
        assert isinstance(result, ExtractionResult)


# --- extract_with_gpu_handoff() tests ---


class TestGpuHandoff:
    """Tests for ClinicalExtractor.extract_with_gpu_handoff()."""

    def test_gpu_handoff_unloads_whisper_before_extraction(
        self,
        extractor: ClinicalExtractor,
        fake_whisper_service: FakeWhisperServiceGpu,
        sample_transcript: str,
    ) -> None:
        """Whisper is unloaded before extraction runs."""
        extractor.extract_with_gpu_handoff(
            sample_transcript, fake_whisper_service
        )
        assert fake_whisper_service.unload_count == 1

    def test_gpu_handoff_unloads_ollama_after_extraction(
        self,
        extractor: ClinicalExtractor,
        fake_ollama_service: FakeOllamaService,
        fake_whisper_service: FakeWhisperServiceGpu,
        sample_transcript: str,
    ) -> None:
        """Ollama model is unloaded after extraction."""
        extractor.extract_with_gpu_handoff(
            sample_transcript, fake_whisper_service
        )
        assert fake_ollama_service.unload_count == 1

    def test_gpu_handoff_reloads_whisper_after_extraction(
        self,
        extractor: ClinicalExtractor,
        fake_whisper_service: FakeWhisperServiceGpu,
        sample_transcript: str,
    ) -> None:
        """Whisper is reloaded after extraction and LLM unload."""
        extractor.extract_with_gpu_handoff(
            sample_transcript, fake_whisper_service
        )
        assert fake_whisper_service.load_model_count == 1
        assert fake_whisper_service.is_loaded is True

    def test_gpu_handoff_returns_extraction_result(
        self,
        extractor: ClinicalExtractor,
        fake_whisper_service: FakeWhisperServiceGpu,
        sample_transcript: str,
    ) -> None:
        """extract_with_gpu_handoff returns valid ExtractionResult."""
        result = extractor.extract_with_gpu_handoff(
            sample_transcript, fake_whisper_service
        )
        assert isinstance(result, ExtractionResult)

    def test_gpu_handoff_reloads_whisper_on_error(
        self,
        settings: Settings,
        fake_whisper_service: FakeWhisperServiceGpu,
        sample_transcript: str,
    ) -> None:
        """Whisper reloaded even when extraction raises (finally block)."""

        class FailingOllama(FakeOllamaService):
            def generate_structured(self, *args, **kwargs):
                raise RuntimeError("LLM inference failed")

        ext = ClinicalExtractor(FailingOllama(), settings)
        with pytest.raises(RuntimeError, match="LLM inference failed"):
            ext.extract_with_gpu_handoff(
                sample_transcript, fake_whisper_service
            )
        # Whisper must still be reloaded
        assert fake_whisper_service.load_model_count == 1
        assert fake_whisper_service.is_loaded is True

    def test_gpu_handoff_sequence(
        self,
        settings: Settings,
        sample_transcript: str,
    ) -> None:
        """Exact call order: whisper.unload -> ollama.generate -> ollama.unload -> whisper.load."""
        call_log: list[str] = []

        whisper = FakeWhisperServiceGpu()
        ollama = FakeOllamaService()

        # Monkey-patch to record call order
        original_whisper_unload = whisper.unload
        original_whisper_load = whisper.load_model
        original_ollama_generate = ollama.generate_structured
        original_ollama_unload = ollama.unload

        def tracked_whisper_unload():
            call_log.append("whisper.unload")
            original_whisper_unload()

        def tracked_whisper_load():
            call_log.append("whisper.load_model")
            original_whisper_load()

        def tracked_ollama_generate(*args, **kwargs):
            call_log.append("ollama.generate_structured")
            return original_ollama_generate(*args, **kwargs)

        def tracked_ollama_unload():
            call_log.append("ollama.unload")
            original_ollama_unload()

        whisper.unload = tracked_whisper_unload
        whisper.load_model = tracked_whisper_load
        ollama.generate_structured = tracked_ollama_generate
        ollama.unload = tracked_ollama_unload

        ext = ClinicalExtractor(ollama, settings)
        ext.extract_with_gpu_handoff(sample_transcript, whisper)

        assert call_log == [
            "whisper.unload",
            "ollama.generate_structured",
            "ollama.unload",
            "whisper.load_model",
        ]
