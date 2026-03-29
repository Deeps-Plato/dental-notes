"""Pydantic models for clinical extraction output.

Defines the structured output schema used by Ollama's format parameter
to constrain LLM output to valid dental SOAP notes with CDT codes.
Includes appointment type classification and patient summary models.
"""

from enum import Enum

from pydantic import BaseModel, Field


class AppointmentType(str, Enum):
    """Dental appointment type for template-specific extraction.

    Used to select prompt overlays that emphasize different clinical
    details per appointment type. GENERAL is the default when no
    specific type is selected or auto-detection is uncertain.
    """

    GENERAL = "general"
    COMPREHENSIVE_EXAM = "comprehensive_exam"
    RESTORATIVE = "restorative"
    HYGIENE_RECALL = "hygiene_recall"
    ENDODONTIC = "endodontic"
    ORAL_SURGERY = "oral_surgery"


class PatientSummary(BaseModel):
    """Plain-language patient summary at ~6th-grade reading level.

    Generated from the transcript (not the SOAP note) to avoid
    clinical jargon bleed. Intended as a patient handout.
    """

    what_we_did: str = Field(
        description="Plain-language summary of procedures and findings from today's visit"
    )
    whats_next: str = Field(
        description="Upcoming appointments, follow-up instructions, what to expect"
    )
    home_care: str = Field(
        description="Post-visit care instructions, medications, dietary restrictions"
    )


class CdtCode(BaseModel):
    """A CDT dental procedure code suggestion."""

    code: str = Field(pattern=r"^D\d{4}$", description="CDT code, e.g. D2391")
    description: str = Field(description="Procedure description")


class SpeakerChunk(BaseModel):
    """A re-attributed transcript chunk with speaker label."""

    chunk_id: int
    speaker: str = Field(description="Doctor, Patient, or Assistant")
    text: str


class SoapNote(BaseModel):
    """Structured dental SOAP note with CDT code suggestions."""

    subjective: str = Field(
        description=(
            "Narrative paragraph: chief complaint, location, onset/duration, "
            "pain quality/severity, aggravating/relieving factors, dental history"
        )
    )
    objective: str = Field(
        description=(
            "Narrative of all clinical and radiographic findings: tooth numbers, "
            "existing restorations and their condition, cracks, proximity to pulp, "
            "periapical status, percussion/palpation results"
        )
    )
    assessment: str = Field(
        description="Diagnoses with tooth numbers, classification, differentials, prognosis"
    )
    plan: str = Field(
        description=(
            "All procedures planned with tooth numbers, materials, contingency plans, "
            "follow-up, patient instructions, referrals"
        )
    )
    cdt_codes: list[CdtCode] = Field(
        description=(
            "ALL CDT codes for services performed and planned: "
            "exam type, radiographs taken, procedures completed or planned"
        )
    )
    clinical_discussion: list[str] = Field(
        description=(
            "Bullet-point summary of clinical reasoning discussed with "
            "patient: diagnosis explanation, analogies used, risks/benefits, "
            "treatment alternatives, and rationale for chosen plan"
        ),
    )
    medications: list[str] = Field(
        default_factory=list,
        description=(
            "ONLY medications explicitly prescribed in transcript. "
            "Empty list if none discussed -- never infer standard medications"
        ),
    )
    va_narrative: str | None = Field(
        default=None,
        description=(
            "Per-tooth narrative for VA patients "
            "(auto-detected from transcript context)"
        ),
    )


class ExtractionResult(BaseModel):
    """Complete output from clinical extraction pipeline.

    Contains the structured SOAP note, re-attributed speaker chunks,
    a one-sentence clinical summary, and an optional patient summary.
    """

    soap_note: SoapNote
    speaker_chunks: list[SpeakerChunk]
    clinical_summary: str = Field(description="One-sentence summary of the visit")
    patient_summary: PatientSummary | None = Field(
        default=None,
        description="Plain-language patient handout (generated separately)",
    )
