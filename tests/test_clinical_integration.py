"""Integration tests for the clinical extraction pipeline.

These tests require a real Ollama instance running at localhost:11434
with a Qwen3 model pulled (8b or 4b). They are marked with
@pytest.mark.integration and skipped by default. Run with:

    pytest tests/test_clinical_integration.py --integration -x --tb=short -v

Each LLM call may take 30-60 seconds. Total suite: ~3-5 minutes.
"""

import re

import pytest

from dental_notes.clinical.models import ExtractionResult, SpeakerChunk
from tests.conftest import FakeWhisperServiceGpu, SAMPLE_DENTAL_TRANSCRIPT

pytestmark = pytest.mark.integration


class TestOllamaConnectivity:
    """Verify Ollama service is reachable and model is ready."""

    def test_ollama_available(self, integration_ollama_service):
        assert integration_ollama_service.is_available()

    def test_model_ready(self, integration_ollama_service):
        assert integration_ollama_service.is_model_ready()


class TestClinicalExtraction:
    """Test ClinicalExtractor with real LLM inference."""

    def test_extraction_produces_soap_note(
        self, integration_extractor, sample_transcript
    ):
        result = integration_extractor.extract(sample_transcript)
        assert isinstance(result, ExtractionResult)
        assert result.soap_note.subjective
        assert result.soap_note.objective
        assert result.soap_note.assessment
        assert result.soap_note.plan

    def test_extraction_soap_subjective_mentions_sensitivity(
        self, integration_extractor, sample_transcript
    ):
        result = integration_extractor.extract(sample_transcript)
        subjective_lower = result.soap_note.subjective.lower()
        # Should mention tooth sensitivity or chief complaint
        assert any(
            term in subjective_lower
            for term in ["sensitiv", "cold", "complaint", "upper right"]
        ), (
            f"Subjective should mention sensitivity/complaint, "
            f"got: {result.soap_note.subjective}"
        )

    def test_extraction_soap_objective_mentions_tooth_14(
        self, integration_extractor, sample_transcript
    ):
        result = integration_extractor.extract(sample_transcript)
        objective_lower = result.soap_note.objective.lower()
        # Should reference tooth 14 or clinical findings
        assert any(
            term in objective_lower
            for term in ["14", "#14", "tooth 14", "mesial", "probing"]
        ), (
            f"Objective should mention tooth 14 or findings, "
            f"got: {result.soap_note.objective}"
        )

    def test_extraction_cdt_codes_valid(
        self, integration_extractor, sample_transcript
    ):
        result = integration_extractor.extract(sample_transcript)
        assert len(result.soap_note.cdt_codes) > 0
        cdt_pattern = re.compile(r"^D\d{4}$")
        for code in result.soap_note.cdt_codes:
            assert cdt_pattern.match(code.code), (
                f"CDT code {code.code!r} does not match D####"
            )

    def test_extraction_cdt_codes_include_restoration(
        self, integration_extractor, sample_transcript
    ):
        result = integration_extractor.extract(sample_transcript)
        codes = [c.code for c in result.soap_note.cdt_codes]
        # D2391-D2394 are posterior composite codes; D2140-D2161 are amalgam
        restoration_codes = {
            f"D{n}" for n in range(2140, 2162)
        } | {f"D{n}" for n in range(2391, 2395)}
        has_restoration = any(c in restoration_codes for c in codes)
        assert has_restoration, (
            f"Expected at least one restoration code "
            f"(D2140-D2161 or D2391-D2394), got: {codes}"
        )

    def test_extraction_filters_chitchat(
        self, integration_extractor, sample_transcript
    ):
        result = integration_extractor.extract(sample_transcript)
        soap_text = (
            result.soap_note.subjective
            + result.soap_note.objective
            + result.soap_note.assessment
            + result.soap_note.plan
        ).lower()
        assert "how are you" not in soap_text, (
            "SOAP note should not contain social greeting"
        )
        assert "doing well" not in soap_text, (
            "SOAP note should not contain social response"
        )


class TestSpeakerReattribution:
    """Test SpeakerReattributor with real LLM inference."""

    def test_reattribution_preserves_chunks(
        self, integration_reattributor, sample_chunks
    ):
        result = integration_reattributor.reattribute(sample_chunks)
        assert len(result) == len(sample_chunks)

    def test_reattribution_labels_valid(
        self, integration_reattributor, sample_chunks
    ):
        result = integration_reattributor.reattribute(sample_chunks)
        for chunk in result:
            assert isinstance(chunk, SpeakerChunk)
            assert chunk.speaker in ("Doctor", "Patient"), (
                f"Invalid speaker label: {chunk.speaker!r}"
            )


class TestGpuHandoff:
    """Test GPU handoff with real Ollama but fake Whisper."""

    def test_gpu_handoff_with_fake_whisper(
        self, integration_extractor, sample_transcript
    ):
        """Verify extract_with_gpu_handoff() sequences Whisper unload/reload.

        Uses real Ollama for LLM inference but FakeWhisperServiceGpu
        to verify the GPU memory management sequence without needing
        a real Whisper model.
        """
        fake_whisper = FakeWhisperServiceGpu()
        result = integration_extractor.extract_with_gpu_handoff(
            sample_transcript, fake_whisper
        )
        assert isinstance(result, ExtractionResult)
        assert result.soap_note.subjective
        assert fake_whisper.unload_count == 1
        assert fake_whisper.load_model_count == 1
        assert fake_whisper.is_loaded  # Whisper restored after handoff


class TestFullPipeline:
    """Test the complete pipeline: extraction then reattribution."""

    def test_extraction_then_reattribution(
        self,
        integration_extractor,
        integration_reattributor,
        sample_chunks,
        sample_transcript,
    ):
        extraction = integration_extractor.extract(sample_transcript)
        assert isinstance(extraction, ExtractionResult)

        reattributed = integration_reattributor.reattribute(sample_chunks)
        assert len(reattributed) == len(sample_chunks)

    def test_unload_after_extraction(
        self,
        integration_ollama_service,
        integration_extractor,
        sample_transcript,
    ):
        integration_extractor.extract(sample_transcript)
        integration_ollama_service.unload()  # Should not raise
