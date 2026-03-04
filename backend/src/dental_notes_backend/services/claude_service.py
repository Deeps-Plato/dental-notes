"""Anthropic Claude API calls + prompt dispatch.

All calls are synchronous (run in FastAPI's threadpool via run_in_executor or
directly from an async endpoint using asyncio.to_thread).
"""

from __future__ import annotations

import json
import logging

import anthropic

from dental_notes_backend.config import settings
from dental_notes_backend.models.api_models import (
    GenerateNoteRequest,
    MedicationExtractResponse,
    PerioParseResponse,
    SoapNoteResponse,
)
from dental_notes_backend.prompts.medication_extract import MEDICATION_SYSTEM_PROMPT
from dental_notes_backend.prompts.perio_parse import PERIO_SYSTEM_PROMPT
from dental_notes_backend.prompts.soap_note import SOAP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def generate_soap(req: GenerateNoteRequest) -> SoapNoteResponse:
    """Generate a structured dental SOAP note from a transcript."""
    user_content = req.transcript
    if req.patient_context:
        user_content = f"[Clinical context: {req.patient_context}]\n\n{req.transcript}"

    message = get_client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SOAP_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = _extract_text(message)
    data = _parse_json(raw, "SOAP note")
    return SoapNoteResponse.model_validate(data)


def generate_perio_parse(req: GenerateNoteRequest) -> PerioParseResponse:
    """Parse dictated periodontal readings from a transcript."""
    message = get_client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=PERIO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": req.transcript}],
    )
    raw = _extract_text(message)
    data = _parse_json(raw, "perio parse")
    return PerioParseResponse.model_validate(data)


def generate_medication_extract(req: GenerateNoteRequest) -> MedicationExtractResponse:
    """Extract medication changes from a transcript."""
    message = get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=MEDICATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": req.transcript}],
    )
    raw = _extract_text(message)
    data = _parse_json(raw, "medication extract")
    return MedicationExtractResponse.model_validate(data)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_text(message: anthropic.types.Message) -> str:
    for block in message.content:
        if block.type == "text":
            return block.text
    raise ValueError("Claude response contained no text block")


def _parse_json(raw: str, label: str) -> dict:  # type: ignore[type-arg]
    """Strip markdown fences if present, then parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first fence line and last fence line
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse %s JSON: %s\nRaw: %s", label, exc, raw[:500])
        raise ValueError(f"Claude returned invalid JSON for {label}: {exc}") from exc
