"""Clipboard text formatter for SOAP notes and patient summaries.

Produces plain text with section headers for one-click clipboard copy.
Supports both full-note formatting and per-section formatting for
granular copying. User edits (edited_note dict) take priority over
the AI-generated SoapNote when both are provided.

Also provides format_patient_summary_for_clipboard() for plain-language
patient handouts.
"""

from dental_notes.clinical.models import CdtCode, PatientSummary, SoapNote


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
        values["chief_complaint"] = soap_note.chief_complaint
        values["subjective"] = soap_note.subjective
        values["history"] = soap_note.history
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
        ("chief_complaint", "Chief Complaint"),
        ("subjective", "Subjective"),
        ("history", "History"),
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


def format_patient_summary_for_clipboard(
    patient_summary: PatientSummary | dict,
) -> str:
    """Format a patient summary as plain text for clipboard copy or printing.

    Accepts either a PatientSummary model or a dict with the same keys.
    Returns plain text with section headers: WHAT WE DID TODAY, WHAT COMES
    NEXT, HOME CARE INSTRUCTIONS. Sections separated by blank lines.
    """
    if isinstance(patient_summary, PatientSummary):
        data = patient_summary.model_dump()
    else:
        data = patient_summary

    sections = [
        ("WHAT WE DID TODAY", data.get("what_we_did", "")),
        ("WHAT COMES NEXT", data.get("whats_next", "")),
        ("HOME CARE INSTRUCTIONS", data.get("home_care", "")),
    ]

    formatted: list[str] = []
    for header, content in sections:
        if content:
            formatted.append(f"{header}\n{content}")

    return "\n\n".join(formatted)
