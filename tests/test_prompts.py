"""Tests for template composition, patient summary prompt, and appointment type classification.

Tests cover:
- TEMPLATE_OVERLAYS has entries for all non-general appointment types
- Each overlay is short (under 500 chars)
- compose_extraction_prompt() returns correct prompts for all template types
- PATIENT_SUMMARY_PROMPT meets content requirements (6th-grade, forbidden terms, transcript input)
- APPOINTMENT_TYPE_CLASSIFICATION_PROMPT lists all appointment types with "general" fallback
"""

import re


class TestTemplateOverlays:
    """TEMPLATE_OVERLAYS dict has keys for all non-general appointment types."""

    def test_has_comprehensive_exam(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert "comprehensive_exam" in TEMPLATE_OVERLAYS

    def test_has_restorative(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert "restorative" in TEMPLATE_OVERLAYS

    def test_has_hygiene_recall(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert "hygiene_recall" in TEMPLATE_OVERLAYS

    def test_has_endodontic(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert "endodontic" in TEMPLATE_OVERLAYS

    def test_has_oral_surgery(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert "oral_surgery" in TEMPLATE_OVERLAYS

    def test_does_not_have_general(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert "general" not in TEMPLATE_OVERLAYS

    def test_has_exactly_five_entries(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        assert len(TEMPLATE_OVERLAYS) == 5

    def test_each_overlay_under_500_chars(self):
        from dental_notes.clinical.prompts import TEMPLATE_OVERLAYS

        for key, overlay in TEMPLATE_OVERLAYS.items():
            assert len(overlay) < 500, (
                f"Overlay '{key}' is {len(overlay)} chars, should be < 500"
            )


class TestComposeExtractionPrompt:
    """compose_extraction_prompt() returns correct composed prompts."""

    def test_none_returns_base_prompt(self):
        from dental_notes.clinical.prompts import (
            EXTRACTION_SYSTEM_PROMPT,
            compose_extraction_prompt,
        )

        result = compose_extraction_prompt(None)
        assert result == EXTRACTION_SYSTEM_PROMPT

    def test_general_returns_base_prompt(self):
        from dental_notes.clinical.prompts import (
            EXTRACTION_SYSTEM_PROMPT,
            compose_extraction_prompt,
        )

        result = compose_extraction_prompt("general")
        assert result == EXTRACTION_SYSTEM_PROMPT

    def test_restorative_appends_overlay(self):
        from dental_notes.clinical.prompts import (
            EXTRACTION_SYSTEM_PROMPT,
            TEMPLATE_OVERLAYS,
            compose_extraction_prompt,
        )

        result = compose_extraction_prompt("restorative")
        assert result.startswith(EXTRACTION_SYSTEM_PROMPT)
        assert TEMPLATE_OVERLAYS["restorative"] in result
        assert len(result) > len(EXTRACTION_SYSTEM_PROMPT)

    def test_comprehensive_exam_includes_emphasis(self):
        from dental_notes.clinical.prompts import compose_extraction_prompt

        result = compose_extraction_prompt("comprehensive_exam")
        # Should mention full-mouth or comprehensive concepts
        lower = result.lower()
        assert "full-mouth" in lower or "comprehensive" in lower or "perio" in lower

    def test_hygiene_recall_includes_emphasis(self):
        from dental_notes.clinical.prompts import compose_extraction_prompt

        result = compose_extraction_prompt("hygiene_recall")
        lower = result.lower()
        assert "probing" in lower or "bop" in lower or "home care" in lower

    def test_endodontic_includes_emphasis(self):
        from dental_notes.clinical.prompts import compose_extraction_prompt

        result = compose_extraction_prompt("endodontic")
        lower = result.lower()
        assert "canal" in lower or "vitality" in lower or "obturation" in lower

    def test_oral_surgery_includes_emphasis(self):
        from dental_notes.clinical.prompts import compose_extraction_prompt

        result = compose_extraction_prompt("oral_surgery")
        lower = result.lower()
        assert "surgical" in lower or "suture" in lower or "hemostasis" in lower


class TestPatientSummaryPrompt:
    """PATIENT_SUMMARY_PROMPT meets content requirements."""

    def test_contains_sixth_grade_reading_level(self):
        from dental_notes.clinical.prompts import PATIENT_SUMMARY_PROMPT

        lower = PATIENT_SUMMARY_PROMPT.lower()
        assert "6th-grade" in lower or "6th grade" in lower

    def test_contains_forbidden_terms(self):
        from dental_notes.clinical.prompts import PATIENT_SUMMARY_PROMPT

        lower = PATIENT_SUMMARY_PROMPT.lower()
        assert "cdt" in lower or "forbidden" in lower or "do not use" in lower

    def test_instructs_transcript_input(self):
        from dental_notes.clinical.prompts import PATIENT_SUMMARY_PROMPT

        lower = PATIENT_SUMMARY_PROMPT.lower()
        assert "transcript" in lower

    def test_has_three_sections(self):
        from dental_notes.clinical.prompts import PATIENT_SUMMARY_PROMPT

        lower = PATIENT_SUMMARY_PROMPT.lower()
        assert "what we did" in lower or "what_we_did" in lower
        assert "what comes next" in lower or "whats_next" in lower or "what's next" in lower
        assert "home care" in lower or "home_care" in lower

    def test_has_max_word_limit(self):
        from dental_notes.clinical.prompts import PATIENT_SUMMARY_PROMPT

        assert "250" in PATIENT_SUMMARY_PROMPT or "word" in PATIENT_SUMMARY_PROMPT.lower()


class TestAppointmentTypeClassificationPrompt:
    """APPOINTMENT_TYPE_CLASSIFICATION_PROMPT classifies transcripts."""

    def test_prompt_exists(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert isinstance(APPOINTMENT_TYPE_CLASSIFICATION_PROMPT, str)
        assert len(APPOINTMENT_TYPE_CLASSIFICATION_PROMPT) > 50

    def test_lists_comprehensive_exam(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert "comprehensive_exam" in APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

    def test_lists_restorative(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert "restorative" in APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

    def test_lists_hygiene_recall(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert "hygiene_recall" in APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

    def test_lists_endodontic(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert "endodontic" in APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

    def test_lists_oral_surgery(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert "oral_surgery" in APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

    def test_instructs_general_fallback(self):
        from dental_notes.clinical.prompts import APPOINTMENT_TYPE_CLASSIFICATION_PROMPT

        assert "general" in APPOINTMENT_TYPE_CLASSIFICATION_PROMPT.lower()
