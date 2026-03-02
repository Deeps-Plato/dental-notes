"""POST /generate-note — transcript → structured dental note via Claude."""

import asyncio

from fastapi import APIRouter, HTTPException

from dental_notes_backend.models.api_models import (
    GenerateNoteRequest,
    MedicationExtractResponse,
    PerioParseResponse,
    SoapNoteResponse,
)
from dental_notes_backend.services import claude_service

router = APIRouter()


@router.post(
    "/generate-note",
    response_model=SoapNoteResponse | PerioParseResponse | MedicationExtractResponse,
)
async def generate_note(
    req: GenerateNoteRequest,
) -> SoapNoteResponse | PerioParseResponse | MedicationExtractResponse:
    """Generate a structured note from a transcript.

    Runs the synchronous Claude SDK call in a threadpool to avoid blocking
    the event loop.
    """
    try:
        match req.note_type:
            case "soap":
                return await asyncio.to_thread(claude_service.generate_soap, req)
            case "perio_parse":
                return await asyncio.to_thread(claude_service.generate_perio_parse, req)
            case "medication_extract":
                return await asyncio.to_thread(claude_service.generate_medication_extract, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Note generation failed: {exc}") from exc
