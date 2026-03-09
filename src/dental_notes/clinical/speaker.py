"""Speaker re-attribution using LLM conversational context analysis.

SpeakerReattributor takes transcript chunks with potentially incorrect
keyword-based speaker labels and uses the LLM to correct them based on
conversational context (clinical terminology -> Doctor, symptom reports -> Patient).
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from dental_notes.clinical.models import SpeakerChunk
from dental_notes.config import Settings

logger = logging.getLogger(__name__)

SPEAKER_SYSTEM_PROMPT = """You are a dental appointment transcript analyst. \
Your task is to correct speaker labels (Doctor or Patient) for each chunk \
of a dental appointment transcript.

## Speaker Attribution Rules
- DOCTOR: leads conversation, uses clinical terminology, gives diagnoses, \
instructs patient, directs procedures
- PATIENT: responds to questions, reports symptoms in lay language, asks \
personal questions, acknowledges instructions
- Maintain speaker continuity across pauses -- same speaker unless clear \
turn-taking signal
- A speaker who was mid-thought and paused is still the same speaker in \
the next chunk

## Input Format
You receive numbered transcript chunks with current speaker labels \
(which may be incorrect).

## Output Format
Return a JSON object with a "chunks" array of objects, each with \
chunk_id, speaker, and text fields. You MUST return exactly the same \
number of chunks as the input. Do NOT change the text content -- only \
correct the speaker labels."""


class _SpeakerChunkList(BaseModel):
    """Wrapper model for LLM output: list of speaker chunks."""

    chunks: list[SpeakerChunk]


class SpeakerReattributor:
    """Corrects speaker labels using LLM conversational context analysis.

    Takes (speaker, text) chunk tuples with potentially incorrect
    keyword-based labels and returns SpeakerChunk objects with
    corrected Doctor/Patient attribution.
    """

    def __init__(self, ollama_service, settings: Settings) -> None:
        self._ollama = ollama_service
        self._settings = settings

    def reattribute(
        self, chunks: list[tuple[str, str]]
    ) -> list[SpeakerChunk]:
        """Re-attribute speaker labels for transcript chunks.

        Args:
            chunks: List of (speaker, text) tuples from SessionManager.

        Returns:
            List of SpeakerChunk with corrected speaker labels.

        Raises:
            ValueError: If LLM returns invalid JSON or wrong chunk count.
        """
        if not chunks:
            return []

        formatted = "\n".join(
            f"[{i}] {speaker}: {text}"
            for i, (speaker, text) in enumerate(chunks)
        )

        schema = _SpeakerChunkList.model_json_schema()
        raw_json = self._ollama.generate_structured(
            system_prompt=SPEAKER_SYSTEM_PROMPT,
            user_content=formatted,
            schema=schema,
            temperature=self._settings.ollama_temperature,
            num_ctx=self._settings.ollama_num_ctx,
        )

        try:
            parsed = _SpeakerChunkList.model_validate_json(raw_json)
        except ValidationError as e:
            raise ValueError(
                f"LLM returned invalid speaker data: {e}"
            ) from e

        if len(parsed.chunks) != len(chunks):
            raise ValueError(
                f"Speaker re-attribution chunk count mismatch: "
                f"expected {len(chunks)}, got {len(parsed.chunks)}"
            )

        return parsed.chunks
