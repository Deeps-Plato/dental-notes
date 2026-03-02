"""Pydantic request/response shapes for all API routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── /transcribe ───────────────────────────────────────────────────────────────


class TranscribeResponse(BaseModel):
    transcript: str
    duration_seconds: float
    language: str


# ── /generate-note — shared ───────────────────────────────────────────────────


class GenerateNoteRequest(BaseModel):
    note_type: Literal["soap", "perio_parse", "medication_extract"]
    transcript: str
    # Optional context the caller may supply to improve accuracy
    patient_context: str | None = Field(
        default=None,
        description="Non-identifying clinical context, e.g. 'adult, no known allergies'",
    )


# ── SOAP note ─────────────────────────────────────────────────────────────────


class SoapObjective(BaseModel):
    clinical_findings: str
    radiographic_findings: str | None = None
    vitals: str | None = None


class SoapPlan(BaseModel):
    today: list[str] = Field(default_factory=list)
    next_visit: list[str] = Field(default_factory=list)
    patient_instructions: list[str] = Field(default_factory=list)
    cdt_codes: list[str] = Field(default_factory=list)


class MedicationChange(BaseModel):
    drug_name: str
    dose: str
    frequency: str
    change_type: Literal["prescribed", "discontinued", "modified", "refilled"]
    prescribing_note: str | None = None


class SoapNoteResponse(BaseModel):
    subjective: str
    objective: SoapObjective
    assessment: str
    plan: SoapPlan
    medication_changes: list[MedicationChange] = Field(default_factory=list)


# ── Perio parse ───────────────────────────────────────────────────────────────


class PerioReading(BaseModel):
    tooth: int = Field(ge=1, le=32)
    surface: Literal["buccal", "lingual"]
    depths: list[int] = Field(min_length=3, max_length=3)
    bop: bool = False
    recession: int = Field(default=0, ge=0)


class PerioParseResponse(BaseModel):
    readings: list[PerioReading]
    unparsed_segments: list[str] = Field(default_factory=list)


# ── Medication extract ────────────────────────────────────────────────────────


class MedicationExtractResponse(BaseModel):
    changes: list[MedicationChange] = Field(default_factory=list)
