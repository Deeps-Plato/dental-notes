"""Tests for dental_notes.session.transcript_writer.TranscriptWriter."""

import re
from pathlib import Path

import pytest

from dental_notes.session.transcript_writer import TranscriptWriter


class TestTranscriptWriter:
    """Test crash-safe transcript writer."""

    def test_file_created_with_correct_naming(self, tmp_path: Path):
        """File is created with session_YYYYMMDD_HHMMSS.txt pattern."""
        writer = TranscriptWriter(output_dir=tmp_path)
        assert writer.path.exists()
        assert re.match(r"session_\d{8}_\d{6}\.txt", writer.path.name)
        writer.close()

    def test_append_writes_text(self, tmp_path: Path):
        """append() writes text to the file and it can be read back."""
        writer = TranscriptWriter(output_dir=tmp_path)
        writer.append("The patient presents with a fractured crown.")
        writer.close()

        content = writer.path.read_text()
        assert "The patient presents with a fractured crown." in content

    def test_multiple_appends_accumulate(self, tmp_path: Path):
        """Multiple appends accumulate text in the file."""
        writer = TranscriptWriter(output_dir=tmp_path)
        writer.append("First chunk. ")
        writer.append("Second chunk. ")
        writer.append("Third chunk.")
        writer.close()

        content = writer.path.read_text()
        assert "First chunk." in content
        assert "Second chunk." in content
        assert "Third chunk." in content

    def test_flush_per_chunk(self, tmp_path: Path):
        """After append, file content is readable even without close()."""
        writer = TranscriptWriter(output_dir=tmp_path)
        writer.append("Immediate flush test.")

        # Read file while still open -- should see content due to fsync
        content = writer.path.read_text()
        assert "Immediate flush test." in content
        writer.close()

    def test_output_directory_auto_created(self, tmp_path: Path):
        """Output directory is auto-created if it doesn't exist."""
        nested_dir = tmp_path / "deep" / "nested" / "transcripts"
        assert not nested_dir.exists()

        writer = TranscriptWriter(output_dir=nested_dir)
        assert nested_dir.exists()
        writer.append("test")
        writer.close()

    def test_context_manager(self, tmp_path: Path):
        """Context manager properly opens and closes file."""
        with TranscriptWriter(output_dir=tmp_path) as writer:
            writer.append("Context manager test.")
            file_path = writer.path

        # File should still exist and contain the text
        content = file_path.read_text()
        assert "Context manager test." in content

    def test_path_property(self, tmp_path: Path):
        """path property returns the Path to the transcript file."""
        writer = TranscriptWriter(output_dir=tmp_path)
        assert isinstance(writer.path, Path)
        assert writer.path.parent == tmp_path
        writer.close()
