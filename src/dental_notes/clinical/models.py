"""Pydantic models for clinical extraction output.

Defines the structured output schema used by Ollama's format parameter
to constrain LLM output to valid dental SOAP notes with CDT codes.
"""

from pydantic import BaseModel, Field


class CdtCode(BaseModel):
    """A CDT dental procedure code suggestion."""

    code: str = Field(pattern=r"^D\d{4}$", description="CDT code, e.g. D2391")
    description: str = Field(description="Procedure description")


class SpeakerChunk(BaseModel):
    """A re-attributed transcript chunk with speaker label."""

    chunk_id: int
    speaker: str = Field(description="Doctor or Patient")
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
    and a one-sentence clinical summary.
    """

    soap_note: SoapNote
    speaker_chunks: list[SpeakerChunk]
    clinical_summary: str = Field(description="One-sentence summary of the visit")
