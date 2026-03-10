"""Clipboard text formatter for SOAP notes.

Produces plain text with section headers for one-click clipboard copy.
Supports both full-note formatting and per-section formatting for
granular copying. User edits (edited_note dict) take priority over
the AI-generated SoapNote when both are provided.
"""

from dental_notes.clinical.models import CdtCode, SoapNote


def format_section(
    section_name: str,
    content: str | list | None,
) -> str:
    """Format a single section for per-section copy.

    Handles:
    - str: narrative sections (Subjective, Objective, etc.)
    - list[str]: bullet-pointed sections (Clinical Discussion, Medications)
    - list[CdtCode]: CDT code formatting ("D1234 - Description")
    - None or empty: returns empty string
    """
    if content is None:
        return ""
    if isinstance(content, str):
        if not content.strip():
            return ""
        return f"{section_name}:\n{content}"
    if isinstance(content, list):
        if not content:
            return ""
        # Check if items are CdtCode objects
        if content and isinstance(content[0], CdtCode):
            lines = [f"{code.code} - {code.description}" for code in content]
            return f"{section_name}:\n" + "\n".join(lines)
        # Regular list items as bullet points
        lines = [f"- {item}" for item in content]
        return f"{section_name}:\n" + "\n".join(lines)
    return ""


def format_note_for_clipboard(
    soap_note: SoapNote | None = None,
    edited_note: dict | None = None,
) -> str:
    """Format a SOAP note as plain text for clipboard copy.

    If edited_note is provided, its values override the soap_note fields
    (user edits take priority per locked decision). If only edited_note
    is provided without soap_note, formats from the dict alone.

    Section order: Subjective, Objective, Assessment, Plan, CDT Codes,
    Clinical Discussion, Prescribed Medications, VA Per-Tooth Narrative.
    Empty sections are omitted. Sections separated by blank lines.
    """
    if soap_note is None and edited_note is None:
        return ""

    # Build values from soap_note, then override with edited_note
    values: dict[str, str | list | None] = {}

    if soap_note is not None:
        values["subjective"] = soap_note.subjective
        values["objective"] = soap_note.objective
        values["assessment"] = soap_note.assessment
        values["plan"] = soap_note.plan
        values["cdt_codes"] = soap_note.cdt_codes
        values["clinical_discussion"] = soap_note.clinical_discussion
        values["medications"] = soap_note.medications
        values["va_narrative"] = soap_note.va_narrative

    if edited_note is not None:
        for key, val in edited_note.items():
            values[key] = val

    # Ordered sections: name -> (dict key, display name)
    sections = [
        ("subjective", "Subjective"),
        ("objective", "Objective"),
        ("assessment", "Assessment"),
        ("plan", "Plan"),
        ("cdt_codes", "CDT Codes"),
        ("clinical_discussion", "Clinical Discussion"),
        ("medications", "Prescribed Medications"),
        ("va_narrative", "VA Per-Tooth Narrative"),
    ]

    formatted_sections: list[str] = []
    for key, display_name in sections:
        content = values.get(key)
        section_text = format_section(display_name, content)
        if section_text:
            formatted_sections.append(section_text)

    return "\n\n".join(formatted_sections)
