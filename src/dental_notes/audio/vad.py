"""Voice Activity Detection using silero-vad.

Wraps the silero-vad model to classify speech vs silence/noise on 512-sample
sub-chunks at 16kHz. Always runs on CPU to preserve GPU VRAM for Whisper.
"""

import numpy as np

SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # silero-vad requires exactly 512 samples at 16kHz


class VadDetector:
    """Speech/silence classifier using silero-vad.

    Processes audio in 512-sample sub-chunks and returns the max speech
    probability across all sub-chunks.
    """

    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = threshold
        self._model = self._load_model()

    @staticmethod
    def _load_model():
        """Load the silero-vad model on CPU."""
        import torch

        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        return model

    def is_speech(self, audio_block: np.ndarray) -> bool:
        """Classify whether the audio block contains speech.

        Returns True if the max speech probability exceeds the threshold.
        """
        return self.get_speech_probability(audio_block) > self._threshold

    def get_speech_probability(self, audio_block: np.ndarray) -> float:
        """Return the max speech probability for the audio block.

        Processes 512-sample sub-chunks and returns the highest probability.
        """
        import torch

        probs: list[float] = []
        for i in range(0, len(audio_block) - (CHUNK_SIZE - 1), CHUNK_SIZE):
            chunk = torch.from_numpy(
                audio_block[i : i + CHUNK_SIZE].copy()
            ).to("cpu")
            prob = self._model(chunk, SAMPLE_RATE).item()
            probs.append(prob)

        return max(probs) if probs else 0.0

    def reset(self) -> None:
        """Reset VAD model state (silero-vad is stateful between calls)."""
        if hasattr(self._model, "reset_states"):
            self._model.reset_states()
