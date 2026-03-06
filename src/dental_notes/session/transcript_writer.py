"""Crash-safe transcript writer with flush-per-chunk and fsync.

Appends each transcribed chunk to a plain text file and flushes immediately,
ensuring content is persisted to disk even if the process crashes.

File naming uses timestamps only (no patient info) for HIPAA alignment.
"""

import os
from datetime import datetime
from pathlib import Path


class TranscriptWriter:
    """Append-to-file writer with flush-per-chunk crash safety.

    Each call to append() writes text, flushes the buffer, and calls
    os.fsync() to ensure data reaches disk. Plain text format with no
    JSON or timestamps (per locked decisions).
    """

    def __init__(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = output_dir / f"session_{timestamp}.txt"
        self._file = open(self._path, "a")  # noqa: SIM115

    @property
    def path(self) -> Path:
        """Return the Path to the transcript file."""
        return self._path

    def append(self, text: str) -> None:
        """Write text and flush immediately to disk (crash-safe).

        Calls flush() and os.fsync() to guarantee data is persisted
        even if the process crashes after this call returns.
        """
        self._file.write(text)
        self._file.flush()
        os.fsync(self._file.fileno())

    def close(self) -> None:
        """Close the file handle."""
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "TranscriptWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
