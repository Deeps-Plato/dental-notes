"""Tests for clipboard text formatter (NoteFormatter).

Tests cover:
- format_note_for_clipboard() produces plain text with section headers
- Sections with empty content are omitted
- CDT codes formatted as "D1234 - Description" per line
- Clinical Discussion formatted as bullet points
- Medications formatted as bullet points at bottom
- VA narrative appended as separate section when present
- VA narrative omitted when None
- format_section() returns single section text
- format from edited_note dict (user edits override extraction_result)
"""

from dental_notes.clinical.models import CdtCode, SoapNote


def _make_soap_note(**overrides) -> SoapNote:
    """Helper to build a SoapNote with defaults."""
    defaults = {
        "subjective": "Patient reports cold sensitivity on upper right.",
        "objective": "Tooth #14 MO discoloration. Probing 2-3mm.",
        "assessment": "Class II caries #14 MO.",
        "plan": "Two-surface composite restoration #14.",
        "cdt_codes": [
            CdtCode(code="D2392", description="Composite 2 surfaces posterior"),
            CdtCode(code="D0220", description="Periapical radiograph"),
        ],
        "clinical_discussion": [
            "Composite chosen over amalgam for aesthetics",
            "Periapical radiograph to rule out nerve involvement",
        ],
        "medications": [],
        "va_narrative": None,
    }
    defaults.update(overrides)
    return SoapNote(**defaults)


class TestFormatNoteForClipboard:
    """format_note_for_clipboard() produces plain text with section headers."""

    def test_contains_all_section_headers(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note()
        text = format_note_for_clipboard(soap_note=note)
        assert "Subjective:" in text
        assert "Objective:" in text
        assert "Assessment:" in text
        assert "Plan:" in text
        assert "CDT Codes:" in text
        assert "Clinical Discussion:" in text

    def test_sections_separated_by_blank_lines(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note()
        text = format_note_for_clipboard(soap_note=note)
        # Each section header should be preceded by a blank line (except first)
        lines = text.split("\n")
        section_indices = [
            i for i, line in enumerate(lines) if line.endswith(":")
        ]
        for idx in section_indices[1:]:
            assert lines[idx - 1] == "", (
                f"Section at line {idx} not preceded by blank line"
            )

    def test_cdt_codes_formatted_as_code_dash_description(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note()
        text = format_note_for_clipboard(soap_note=note)
        assert "D2392 - Composite 2 surfaces posterior" in text
        assert "D0220 - Periapical radiograph" in text

    def test_clinical_discussion_as_bullet_points(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note()
        text = format_note_for_clipboard(soap_note=note)
        assert "- Composite chosen over amalgam for aesthetics" in text
        assert "- Periapical radiograph to rule out nerve involvement" in text

    def test_medications_as_bullet_points(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note(
            medications=["Amoxicillin 500mg TID x7 days", "Ibuprofen 600mg PRN"]
        )
        text = format_note_for_clipboard(soap_note=note)
        assert "Prescribed Medications:" in text
        assert "- Amoxicillin 500mg TID x7 days" in text
        assert "- Ibuprofen 600mg PRN" in text

    def test_medications_at_bottom_before_va(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note(
            medications=["Amoxicillin 500mg"],
            va_narrative="Tooth #14: caries. Indicated: composite.",
        )
        text = format_note_for_clipboard(soap_note=note)
        meds_pos = text.index("Prescribed Medications:")
        va_pos = text.index("VA Per-Tooth Narrative:")
        assert meds_pos < va_pos

    def test_va_narrative_appended_when_present(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note(
            va_narrative="Tooth #14: Class II caries MO. Indicated: composite restoration."
        )
        text = format_note_for_clipboard(soap_note=note)
        assert "VA Per-Tooth Narrative:" in text
        assert "Tooth #14: Class II caries MO" in text

    def test_va_narrative_omitted_when_none(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note(va_narrative=None)
        text = format_note_for_clipboard(soap_note=note)
        assert "VA Per-Tooth Narrative:" not in text

    def test_empty_sections_omitted(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note(
            subjective="",
            medications=[],
            clinical_discussion=[],
            cdt_codes=[],
        )
        text = format_note_for_clipboard(soap_note=note)
        assert "Subjective:" not in text
        assert "Prescribed Medications:" not in text
        assert "Clinical Discussion:" not in text
        assert "CDT Codes:" not in text

    def test_edited_note_dict_overrides_soap_note(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        note = _make_soap_note(subjective="Original subjective.")
        edited = {
            "subjective": "Edited subjective from user.",
            "objective": "Edited objective.",
            "assessment": "Edited assessment.",
            "plan": "Edited plan.",
        }
        text = format_note_for_clipboard(soap_note=note, edited_note=edited)
        assert "Edited subjective from user." in text
        assert "Original subjective." not in text

    def test_edited_note_without_soap_note(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        edited = {
            "subjective": "User-written subjective.",
            "objective": "User-written objective.",
            "assessment": "User-written assessment.",
            "plan": "User-written plan.",
        }
        text = format_note_for_clipboard(edited_note=edited)
        assert "Subjective:" in text
        assert "User-written subjective." in text

    def test_returns_empty_string_when_no_input(self):
        from dental_notes.clinical.formatter import format_note_for_clipboard

        text = format_note_for_clipboard()
        assert text == ""


class TestFormatSection:
    """format_section() returns a single section's text."""

    def test_string_content(self):
        from dental_notes.clinical.formatter import format_section

        result = format_section("Subjective", "Patient reports pain.")
        assert result == "Subjective:\nPatient reports pain."

    def test_list_content_as_bullets(self):
        from dental_notes.clinical.formatter import format_section

        result = format_section("Clinical Discussion", ["Point A", "Point B"])
        assert result == "Clinical Discussion:\n- Point A\n- Point B"

    def test_cdt_code_objects(self):
        from dental_notes.clinical.formatter import format_section

        codes = [
            CdtCode(code="D2392", description="Composite 2 surfaces"),
            CdtCode(code="D0220", description="Periapical radiograph"),
        ]
        result = format_section("CDT Codes", codes)
        assert "D2392 - Composite 2 surfaces" in result
        assert "D0220 - Periapical radiograph" in result

    def test_none_content_returns_empty_string(self):
        from dental_notes.clinical.formatter import format_section

        result = format_section("VA Narrative", None)
        assert result == ""

    def test_empty_string_returns_empty_string(self):
        from dental_notes.clinical.formatter import format_section

        result = format_section("Subjective", "")
        assert result == ""

    def test_empty_list_returns_empty_string(self):
        from dental_notes.clinical.formatter import format_section

        result = format_section("Medications", [])
        assert result == ""
