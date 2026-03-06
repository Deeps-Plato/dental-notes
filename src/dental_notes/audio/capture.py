"""Audio capture via sounddevice InputStream.

Follows the proven producer-consumer pattern from whisper-ptt/ptt.py:
sounddevice callback puts audio blocks into a thread-safe queue without
blocking the PortAudio thread.
"""

import math
import queue

import numpy as np
import sounddevice as sd

from dental_notes.config import Settings

BLOCK_SIZE = 1600  # 100ms at 16kHz


class AudioCapture:
    """Manages audio input stream and block queue.

    The sounddevice callback runs on a PortAudio thread and must never block.
    Audio blocks are placed into a bounded queue (maxsize=200, ~20s buffer).
    If the queue is full, blocks are silently dropped.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._stream: sd.InputStream | None = None
        self._last_block: np.ndarray | None = None

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice on each audio block. Must be non-blocking."""
        block = indata.copy().flatten()
        self._last_block = block
        try:
            self.audio_q.put_nowait(block)
        except queue.Full:
            pass  # Drop silently -- better than blocking the audio thread

    def start(self, device_index: int | None = None) -> None:
        """Open the audio input stream."""
        self._stream = sd.InputStream(
            samplerate=self._settings.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
            device=device_index,
        )
        self._stream.start()

    def stop(self) -> None:
        """Close and abort the audio input stream."""
        if self._stream is not None:
            self._stream.abort()
            self._stream.close()
            self._stream = None

    def get_block(self) -> np.ndarray | None:
        """Get the next audio block from the queue.

        Returns None if no block available within 100ms.
        """
        try:
            return self.audio_q.get(timeout=0.1)
        except queue.Empty:
            return None

    def get_level(self) -> float:
        """Return RMS level of the most recent audio block (for UI meter)."""
        if self._last_block is None:
            return 0.0
        rms = math.sqrt(float(np.mean(self._last_block**2)))
        return rms


def list_input_devices() -> list[dict]:
    """Return available audio input devices."""
    devices = sd.query_devices()
    return [
        {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


def find_device_by_name(name: str) -> int | None:
    """Find device index by partial name match (case-insensitive)."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if name.lower() in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    return None
