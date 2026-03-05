"""POST /generate-note — transcript → structured dental note via Claude."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from dental_notes_backend.models.api_models import (
    GenerateNoteRequest,
    MedicationExtractResponse,
    PerioParseResponse,
    SoapNoteResponse,
)
from dental_notes_backend.services import claude_service

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/generate-note",
    response_model=SoapNoteResponse | PerioParseResponse | MedicationExtractResponse,
)
@limiter.limit("20/minute")
async def generate_note(
    request: Request,
    req: GenerateNoteRequest,
) -> SoapNoteResponse | PerioParseResponse | MedicationExtractResponse:
    """Generate a structured note from a transcript.

    Runs the synchronous Claude SDK call in a threadpool to avoid blocking
    the event loop.
    """
    if not req.transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript cannot be empty")
    logger.info("Generating %s note", req.note_type)
    result: SoapNoteResponse | PerioParseResponse | MedicationExtractResponse
    try:
        match req.note_type:
            case "soap":
                result = await asyncio.to_thread(claude_service.generate_soap, req)
            case "perio_parse":
                result = await asyncio.to_thread(claude_service.generate_perio_parse, req)
            case "medication_extract":
                result = await asyncio.to_thread(
                    claude_service.generate_medication_extract, req,
                )
            case _:
                raise HTTPException(
                    status_code=422, detail=f"Unknown note type: {req.note_type}",
                )
        logger.info("Note generation complete: type=%s", req.note_type)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Note generation failed: {exc}") from exc
