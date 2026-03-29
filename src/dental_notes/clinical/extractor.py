"""Clinical extraction pipeline: transcript to structured SOAP note.

ClinicalExtractor takes dental appointment transcripts and produces
structured ExtractionResult (SOAP note + CDT codes + speaker chunks)
via Ollama LLM inference. Includes GPU handoff for constrained VRAM
hardware (Whisper unload -> LLM -> LLM unload -> Whisper reload).

Supports template-aware extraction via appointment type overlays,
auto-detection of appointment type from transcript, and patient
summary generation as a second LLM call during GPU handoff.
"""

import logging

from pydantic import ValidationError

from dental_notes.clinical.models import (
    AppointmentType,
    ExtractionResult,
    PatientSummary,
)
from dental_notes.clinical.prompts import (
    APPOINTMENT_TYPE_CLASSIFICATION_PROMPT,
    PATIENT_SUMMARY_PROMPT,
    compose_extraction_prompt,
)
from dental_notes.config import Settings

logger = logging.getLogger(__name__)


class ClinicalExtractor:
    """Extracts structured clinical data from dental appointment transcripts.

    Uses OllamaService (injected) to send transcript to local LLM and
    validate the structured JSON response into an ExtractionResult.
    Supports template-aware extraction and patient summary generation.
    """

    def __init__(self, ollama_service, settings: Settings) -> None:
        self._ollama = ollama_service
        self._settings = settings

    def extract(
        self, transcript: str, template_type: str | None = None
    ) -> ExtractionResult:
        """Extract structured clinical data from a transcript string.

        When template_type is None, auto-detects appointment type via
        a lightweight LLM classification call. When template_type is
        a string (including "general"), uses the specified type directly.

        Raises:
            ValueError: If LLM returns JSON that fails Pydantic validation.
        """
        if template_type is None:
            inferred_type = self._infer_appointment_type(transcript)
            system_prompt = compose_extraction_prompt(inferred_type)
        else:
            system_prompt = compose_extraction_prompt(template_type)

        schema = ExtractionResult.model_json_schema()
        raw_json = self._ollama.generate_structured(
            system_prompt=system_prompt,
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
        self, chunks: list[tuple[str, str]], template_type: str | None = None
    ) -> ExtractionResult:
        """Extract from a list of (speaker, text) chunk tuples.

        Formats chunks as labeled transcript text matching
        SessionManager.get_transcript() format, then calls extract().
        """
        transcript = "\n\n".join(
            f"{speaker}: {text}" for speaker, text in chunks
        )
        return self.extract(transcript, template_type=template_type)

    def extract_with_gpu_handoff(
        self,
        transcript: str,
        whisper_service,
        template_type: str | None = None,
    ) -> ExtractionResult:
        """Orchestrate GPU memory for constrained VRAM hardware.

        Sequences: Whisper unload -> LLM inference (SOAP + patient summary)
        -> LLM unload -> Whisper reload. The finally block ensures Whisper
        is always reloaded even if extraction or summary fails.

        Patient summary is generated as a second LLM call between SOAP
        extraction and Ollama unload. Summary failure is graceful -- logs
        a warning and leaves patient_summary as None.
        """
        logger.info("GPU handoff: unloading Whisper to free VRAM for LLM")
        whisper_service.unload()
        try:
            result = self.extract(transcript, template_type=template_type)
            result.patient_summary = self._generate_patient_summary(transcript)
        except Exception:
            # If extract() itself fails, re-raise after finally
            # If only summary fails, we still have the extraction result
            if "result" not in locals():
                raise
            logger.warning(
                "Patient summary generation failed, proceeding without summary",
                exc_info=True,
            )
        finally:
            logger.info("GPU handoff: unloading LLM and reloading Whisper")
            self._ollama.unload()
            whisper_service.load_model()
        return result

    def _infer_appointment_type(self, transcript: str) -> str:
        """Auto-detect appointment type from transcript via lightweight LLM call.

        Truncates transcript to first ~500 words for efficiency. Returns
        a valid AppointmentType value, falling back to "general" on any
        error or unrecognized LLM response.
        """
        try:
            truncated = " ".join(transcript.split()[:500])
            response = self._ollama.generate(
                system_prompt=APPOINTMENT_TYPE_CLASSIFICATION_PROMPT,
                user_content=truncated,
                num_ctx=2048,
            )
            cleaned = response.strip().lower()
            # Validate against known appointment types
            valid_types = {t.value for t in AppointmentType}
            if cleaned in valid_types:
                logger.info("Auto-detected appointment type: %s", cleaned)
                return cleaned
            logger.warning(
                "Unrecognized appointment type '%s', falling back to general",
                cleaned,
            )
            return "general"
        except Exception:
            logger.warning(
                "Appointment type detection failed, falling back to general",
                exc_info=True,
            )
            return "general"

    def _generate_patient_summary(self, transcript: str) -> PatientSummary:
        """Generate plain-language patient summary from transcript.

        Uses PATIENT_SUMMARY_PROMPT with the transcript text (not SOAP note)
        as input to avoid clinical jargon bleed. Uses lower num_ctx (4096)
        for faster generation since summaries are short.

        Raises:
            ValueError: If LLM returns JSON that fails Pydantic validation.
        """
        schema = PatientSummary.model_json_schema()
        raw_json = self._ollama.generate_structured(
            system_prompt=PATIENT_SUMMARY_PROMPT,
            user_content=transcript,
            schema=schema,
            num_ctx=4096,
        )
        try:
            return PatientSummary.model_validate_json(raw_json)
        except ValidationError as e:
            raise ValueError(
                f"LLM returned invalid patient summary: {e}"
            ) from e
