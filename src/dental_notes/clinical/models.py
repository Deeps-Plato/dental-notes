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
        description="Chief complaint, patient-reported symptoms, pain, onset/duration"
    )
    objective: str = Field(
        description="Clinical findings, tooth numbers, surfaces, conditions, radiographic findings"
    )
    assessment: str = Field(
        description="Diagnoses with tooth numbers, classification"
    )
    plan: str = Field(
        description="Procedures planned with CDT codes, materials, follow-up, patient instructions"
    )
    cdt_codes: list[CdtCode] = Field(
        description="Suggested CDT codes from assessment and plan"
    )
    clinical_discussion: list[str] = Field(
        description=(
            "Bullet-point summary of clinical reasoning discussed with "
            "patient: diagnosis explanation, analogies used, risks/benefits, "
            "treatment alternatives, and rationale for chosen plan"
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
