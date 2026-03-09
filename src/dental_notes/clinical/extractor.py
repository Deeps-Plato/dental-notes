"""Clinical extraction pipeline: transcript to structured SOAP note.

ClinicalExtractor takes dental appointment transcripts and produces
structured ExtractionResult (SOAP note + CDT codes + speaker chunks)
via Ollama LLM inference. Includes GPU handoff for constrained VRAM
hardware (Whisper unload -> LLM -> LLM unload -> Whisper reload).
"""

import logging

from pydantic import ValidationError

from dental_notes.clinical.models import ExtractionResult
from dental_notes.clinical.prompts import EXTRACTION_SYSTEM_PROMPT
from dental_notes.config import Settings

logger = logging.getLogger(__name__)


class ClinicalExtractor:
    """Extracts structured clinical data from dental appointment transcripts.

    Uses OllamaService (injected) to send transcript to local LLM and
    validate the structured JSON response into an ExtractionResult.
    """

    def __init__(self, ollama_service, settings: Settings) -> None:
        self._ollama = ollama_service
        self._settings = settings

    def extract(self, transcript: str) -> ExtractionResult:
        """Extract structured clinical data from a transcript string.

        Sends transcript to LLM with SOAP extraction system prompt,
        validates returned JSON against ExtractionResult schema.

        Raises:
            ValueError: If LLM returns JSON that fails Pydantic validation.
        """
        schema = ExtractionResult.model_json_schema()
        raw_json = self._ollama.generate_structured(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_content=transcript,
            schema=schema,
            temperature=self._settings.ollama_temperature,
            num_ctx=self._settings.ollama_num_ctx,
        )
        try:
            return ExtractionResult.model_validate_json(raw_json)
        except ValidationError as e:
            raise ValueError(f"LLM returned invalid clinical data: {e}") from e

    def extract_from_chunks(
        self, chunks: list[tuple[str, str]]
    ) -> ExtractionResult:
        """Extract from a list of (speaker, text) chunk tuples.

        Formats chunks as labeled transcript text matching
        SessionManager.get_transcript() format, then calls extract().
        """
        transcript = "\n\n".join(
            f"{speaker}: {text}" for speaker, text in chunks
        )
        return self.extract(transcript)

    def extract_with_gpu_handoff(
        self, transcript: str, whisper_service
    ) -> ExtractionResult:
        """Orchestrate GPU memory for constrained VRAM hardware.

        Sequences: Whisper unload -> LLM inference -> LLM unload -> Whisper reload.
        The finally block ensures Whisper is always reloaded even if extraction fails.
        """
        logger.info("GPU handoff: unloading Whisper to free VRAM for LLM")
        whisper_service.unload()
        try:
            result = self.extract(transcript)
        finally:
            logger.info("GPU handoff: unloading LLM and reloading Whisper")
            self._ollama.unload()
            whisper_service.load_model()
        return result
