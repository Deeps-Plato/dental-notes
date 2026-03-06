"""Hybrid audio chunking: VAD silence boundaries + max duration cap + overlap.

Accumulates audio blocks from the capture queue. Finalizes chunks when:
1. VAD detects a silence gap >= silence_gap_secs (natural speech boundary)
2. Total duration reaches max_chunk_duration_secs (forced cut)

Each finalized chunk includes ~1s overlap from the previous chunk's tail,
which allows the transcription stitcher to deduplicate repeated words.
"""

import numpy as np

from dental_notes.audio.vad import VadDetector
from dental_notes.config import Settings


class AudioChunker:
    """Produces VAD-bounded speech chunks with overlap.

    Noise-only audio (no speech detected) is skipped when the buffer is empty,
    preventing Whisper hallucinations on dental equipment noise.
    """

    def __init__(self, settings: Settings, vad: VadDetector) -> None:
        self._settings = settings
        self._vad = vad
        self._buffer: list[np.ndarray] = []
        self._total_samples: int = 0
        self._silence_samples: int = 0
        self._has_speech: bool = False

        self._silence_threshold_samples = int(
            settings.silence_gap_secs * settings.sample_rate
        )
        self._max_duration_samples = int(
            settings.max_chunk_duration_secs * settings.sample_rate
        )
        self._overlap_samples = int(settings.overlap_secs * settings.sample_rate)

    def feed(self, audio_block: np.ndarray) -> np.ndarray | None:
        """Feed an audio block and return a finalized chunk if ready.

        Returns:
            A numpy audio array if a chunk is finalized, None otherwise.
        """
        is_speech = self._vad.is_speech(audio_block)
        block_samples = len(audio_block)

        # Skip noise-only blocks when buffer is empty
        if not is_speech and not self._has_speech:
            return None

        # Append block to buffer
        self._buffer.append(audio_block)
        self._total_samples += block_samples

        if is_speech:
            self._silence_samples = 0
            self._has_speech = True
        else:
            self._silence_samples += block_samples

        # Check finalization conditions
        if self._silence_samples >= self._silence_threshold_samples and self._has_speech:
            return self._finalize()

        if self._total_samples >= self._max_duration_samples:
            return self._finalize()

        return None

    def flush(self) -> np.ndarray | None:
        """Finalize whatever is in the buffer (called on session stop).

        Returns None if buffer is empty.
        """
        if not self._buffer or not self._has_speech:
            return None
        return self._finalize()

    def _finalize(self) -> np.ndarray:
        """Concatenate buffer into a single chunk and prepare overlap for next."""
        chunk = np.concatenate(self._buffer)

        # Save overlap for next chunk: last N samples seed the next buffer
        if len(chunk) > self._overlap_samples:
            overlap = chunk[-self._overlap_samples :]
            self._buffer = [overlap]
            self._total_samples = len(overlap)
        else:
            self._buffer = []
            self._total_samples = 0

        self._silence_samples = 0
        self._has_speech = False

        return chunk
