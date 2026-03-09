"""Tests for clinical extraction Pydantic models and config extensions.

Tests cover:
- SoapNote construction and JSON schema generation
- CdtCode validation (valid/invalid code patterns)
- SpeakerChunk construction
- ExtractionResult with nested SoapNote
- Config Ollama settings with defaults and env overrides
- Prompt constants content verification
"""

import pytest
from pydantic import ValidationError


class TestCdtCode:
    """CdtCode validates CDT code format: D followed by 4 digits."""

    def test_valid_code_d2391(self):
        from dental_notes.clinical.models import CdtCode

        code = CdtCode(code="D2391", description="Posterior composite, 1 surface")
        assert code.code == "D2391"
        assert code.description == "Posterior composite, 1 surface"

    def test_valid_code_d0120(self):
        from dental_notes.clinical.models import CdtCode

        code = CdtCode(code="D0120", description="Periodic oral evaluation")
        assert code.code == "D0120"

    def test_rejects_x_prefix(self):
        from dental_notes.clinical.models import CdtCode

        with pytest.raises(ValidationError):
            CdtCode(code="X1234", description="Invalid prefix")

    def test_rejects_too_short(self):
        from dental_notes.clinical.models import CdtCode

        with pytest.raises(ValidationError):
            CdtCode(code="D12", description="Too short")

    def test_rejects_too_long(self):
        from dental_notes.clinical.models import CdtCode

        with pytest.raises(ValidationError):
            CdtCode(code="D12345", description="Too long")

    def test_rejects_no_prefix(self):
        from dental_notes.clinical.models import CdtCode

        with pytest.raises(ValidationError):
            CdtCode(code="1234", description="No D prefix")


class TestSoapNote:
    """SoapNote has four SOAP sections and a list of CdtCode objects."""

    def test_construction_with_valid_data(self):
        from dental_notes.clinical.models import CdtCode, SoapNote

        note = SoapNote(
            subjective="Patient reports cold sensitivity.",
            objective="Tooth #14 discoloration. Probing 2-3mm.",
            assessment="Class II caries #14 MO.",
            plan="Two-surface composite restoration #14.",
            cdt_codes=[
                CdtCode(code="D2392", description="Composite 2 surfaces posterior")
            ],
        )
        assert note.subjective == "Patient reports cold sensitivity."
        assert note.objective == "Tooth #14 discoloration. Probing 2-3mm."
        assert note.assessment == "Class II caries #14 MO."
        assert note.plan == "Two-surface composite restoration #14."
        assert len(note.cdt_codes) == 1
        assert note.cdt_codes[0].code == "D2392"

    def test_model_json_schema_produces_dict_with_properties(self):
        from dental_notes.clinical.models import SoapNote

        schema = SoapNote.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_schema_has_all_four_soap_sections(self):
        from dental_notes.clinical.models import SoapNote

        schema = SoapNote.model_json_schema()
        props = schema["properties"]
        for field in ("subjective", "objective", "assessment", "plan", "cdt_codes"):
            assert field in props, f"Missing field: {field}"

    def test_empty_cdt_codes_list(self):
        from dental_notes.clinical.models import SoapNote

        note = SoapNote(
            subjective="s",
            objective="o",
            assessment="a",
            plan="p",
            cdt_codes=[],
        )
        assert note.cdt_codes == []


class TestSpeakerChunk:
    """SpeakerChunk has chunk_id, speaker, and text fields."""

    def test_construction(self):
        from dental_notes.clinical.models import SpeakerChunk

        chunk = SpeakerChunk(chunk_id=0, speaker="Doctor", text="Open wide please.")
        assert chunk.chunk_id == 0
        assert chunk.speaker == "Doctor"
        assert chunk.text == "Open wide please."


class TestExtractionResult:
    """ExtractionResult wraps SoapNote, speaker_chunks, and clinical_summary."""

    def test_construction_with_nested_soap_note(self):
        from dental_notes.clinical.models import (
            CdtCode,
            ExtractionResult,
            SoapNote,
            SpeakerChunk,
        )

        result = ExtractionResult(
            soap_note=SoapNote(
                subjective="Patient reports pain.",
                objective="Cavity visible on #14.",
                assessment="Caries #14.",
                plan="Restore #14.",
                cdt_codes=[
                    CdtCode(code="D2391", description="Composite 1 surface posterior")
                ],
            ),
            speaker_chunks=[
                SpeakerChunk(chunk_id=0, speaker="Doctor", text="Hello"),
                SpeakerChunk(chunk_id=1, speaker="Patient", text="Hi"),
            ],
            clinical_summary="Patient presents with caries on #14.",
        )
        assert result.soap_note.assessment == "Caries #14."
        assert len(result.speaker_chunks) == 2
        assert result.clinical_summary == "Patient presents with caries on #14."

    def test_model_json_schema_produces_dict(self):
        from dental_notes.clinical.models import ExtractionResult

        schema = ExtractionResult.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema


class TestConfigOllamaSettings:
    """Settings class extended with Ollama configuration fields."""

    def test_ollama_host_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.ollama_host == "http://localhost:11434"

    def test_ollama_model_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.ollama_model == "qwen3:8b"

    def test_ollama_fallback_model_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.ollama_fallback_model == "qwen3:4b"

    def test_ollama_temperature_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.ollama_temperature == 0.0

    def test_ollama_num_ctx_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.ollama_num_ctx == 8192

    def test_ollama_model_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("DENTAL_OLLAMA_MODEL", "qwen3:4b")
        from dental_notes.config import Settings

        s = Settings()
        assert s.ollama_model == "qwen3:4b"


class TestPrompts:
    """EXTRACTION_SYSTEM_PROMPT and CDT_REFERENCE contain required content."""

    def test_system_prompt_contains_soap(self):
        from dental_notes.clinical.prompts import EXTRACTION_SYSTEM_PROMPT

        assert "SOAP" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_contains_cdt(self):
        from dental_notes.clinical.prompts import EXTRACTION_SYSTEM_PROMPT

        assert "CDT" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_contains_doctor(self):
        from dental_notes.clinical.prompts import EXTRACTION_SYSTEM_PROMPT

        assert "Doctor" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_contains_patient(self):
        from dental_notes.clinical.prompts import EXTRACTION_SYSTEM_PROMPT

        assert "Patient" in EXTRACTION_SYSTEM_PROMPT

    def test_system_prompt_contains_d0120(self):
        from dental_notes.clinical.prompts import EXTRACTION_SYSTEM_PROMPT

        assert "D0120" in EXTRACTION_SYSTEM_PROMPT

    def test_cdt_reference_has_at_least_30_codes(self):
        from dental_notes.clinical.prompts import CDT_REFERENCE

        # Count lines matching D followed by 4 digits
        import re

        codes = re.findall(r"D\d{4}", CDT_REFERENCE)
        assert len(codes) >= 30, f"Only found {len(codes)} CDT codes, need >= 30"
