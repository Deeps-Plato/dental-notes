"""Whisper transcription service with dental vocabulary prompting.

Wraps faster-whisper's WhisperModel with lazy loading, int8 compute type
for GTX 1050 compatibility, and a comprehensive dental initial_prompt that
helps Whisper accurately transcribe clinical terminology.

CRITICAL: Uses compute_type="int8" -- GTX 1050 (CC 6.1) does NOT support
float16 in CTranslate2. Using float16 will either fail or silently fall
back to float32 (slower, more VRAM).
"""

import logging

import numpy as np

from dental_notes.config import Settings

logger = logging.getLogger(__name__)

# Comprehensive dental vocabulary prompt for Whisper initial_prompt.
# Source: CONTEXT.md locked decisions + 01-RESEARCH.md code examples.
# Covers: tooth numbering, surfaces, restorative, perio, endo, oral surgery,
#   implants, prosthetics, materials/brands, CDT codes, sleep apnea, clinical terms.
DENTAL_INITIAL_PROMPT = (
    "Dental clinical appointment transcription. "
    # Tooth numbering
    "Universal tooth numbering: teeth 1 through 32, tooth 1, tooth 14, tooth 19, tooth 30. "
    # Surface names and abbreviations
    "Mesial, occlusal, distal, buccal, lingual, facial, incisal. "
    "MOD, DO, BL, MO, OL, MODBL, MI, DI. "
    # Restorative
    "Composite, amalgam, crown, bridge, onlay, inlay, veneer, bonding, bleaching. "
    "E.max, zirconia, PFM, porcelain-fused-to-metal, lithium disilicate. "
    # Perio
    "Prophy, prophylaxis, SRP, scaling and root planing, pocket depth, bleeding on probing, BOP. "
    "Probing depths, gingival margin, recession, furcation, mobility. "
    # Endo
    "Pulpectomy, pulpotomy, access opening, working length, obturation, root canal, "
    "gutta-percha, endodontic. "
    # Oral surgery
    "Simple extraction, surgical extraction, bone grafting, socket preservation, sutures. "
    # Implants and prosthetics
    "Implant, implant crown, abutment, denture, partial denture, flipper, Invisalign. "
    # Materials and brands
    "Shofu, Ivoclar, Filtek, RelyX, Gluma, Dentsply, Kerr. "
    # CDT codes
    "CDT code D0120, D0150, D0220, D0330, D1110, D2391, D2740, D3330, D4341, D7210. "
    # Sleep apnea
    "Sleep apnea, mandibular advancement device, oral appliance. "
    # Clinical terms
    "Caries, cavity, abscess, periapical, radiolucency, calculus, plaque, gingivitis, "
    "periodontitis, occlusion, malocclusion, TMJ, bruxism, fluoride, sealant."
)


class WhisperService:
    """Wrapper around faster-whisper WhisperModel with dental vocabulary.

    The model is NOT loaded on init (lazy loading). Call load_model() before
    transcribe(). This avoids import-time CUDA dependency and allows tests
    to run without a GPU.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None

    def load_model(self) -> None:
        """Load the Whisper model onto GPU.

        Imports faster_whisper inside this method to avoid import-time
        CUDA dependency. Uses int8 compute type for CC 6.1 GPU compatibility.
        """
        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper model: %s (compute_type=%s)",
            self._settings.whisper_model,
            self._settings.compute_type,
        )
        self._model = WhisperModel(
            self._settings.whisper_model,
            device="cuda",
            compute_type=self._settings.compute_type,
        )
        logger.info("Whisper model loaded successfully")

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe an audio chunk using Whisper with dental vocabulary.

        Args:
            audio: Float32 numpy array of audio samples at 16kHz.

        Returns:
            Transcribed text with segments concatenated and stripped.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        segments, _ = self._model.transcribe(
            audio,
            initial_prompt=DENTAL_INITIAL_PROMPT,
            vad_filter=True,
            no_speech_threshold=0.6,
            language="en",
        )

        # Iterate segments, join text with spaces, strip whitespace
        text_parts = [segment.text for segment in segments]
        return " ".join(part.strip() for part in text_parts if part.strip())

    @property
    def is_loaded(self) -> bool:
        """Return True if the Whisper model is loaded."""
        return self._model is not None

    def unload(self) -> None:
        """Release the model and VRAM."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Whisper model unloaded")
