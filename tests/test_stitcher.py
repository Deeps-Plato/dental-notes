"""Tests for dental_notes.transcription.stitcher.deduplicate_overlap."""

import pytest

from dental_notes.transcription.stitcher import deduplicate_overlap


class TestDeduplicateOverlap:
    """Test word-level overlap deduplication at chunk boundaries."""

    def test_single_word_overlap(self):
        """Removes single overlapping word at boundary."""
        result = deduplicate_overlap("the crown on tooth", "tooth fourteen needs")
        assert result == "fourteen needs"

    def test_multi_word_overlap(self):
        """Removes multiple overlapping words at boundary."""
        result = deduplicate_overlap("word one two", "one two three")
        assert result == "three"

    def test_no_overlap_passes_through(self):
        """Returns full new text when no overlap found."""
        result = deduplicate_overlap("the composite", "entirely new text")
        assert result == "entirely new text"

    def test_empty_previous_returns_full_new(self):
        """Empty previous text returns full new text."""
        result = deduplicate_overlap("", "first chunk")
        assert result == "first chunk"

    def test_empty_new_text_returns_empty(self):
        """Empty new text returns empty string."""
        result = deduplicate_overlap("some previous text", "")
        assert result == ""

    def test_max_overlap_words_limits_window(self):
        """max_overlap_words parameter limits comparison window."""
        # "a b c d e f" tail 3 = "d e f", new starts with "d e f g"
        result = deduplicate_overlap(
            "a b c d e f",
            "d e f g",
            max_overlap_words=3,
        )
        assert result == "g"

        # With window of 1, only "f" is checked -- "d e f" not in window
        result_small = deduplicate_overlap(
            "a b c d e f",
            "d e f g",
            max_overlap_words=1,
        )
        # Only last 1 word "f" compared; "d e f" doesn't match single "f"
        assert result_small == "d e f g"

    def test_single_word_texts(self):
        """Handles single-word texts correctly."""
        result = deduplicate_overlap("hello", "hello world")
        assert result == "world"

    def test_identical_texts(self):
        """Handles identical texts -- full overlap."""
        result = deduplicate_overlap("same words here", "same words here")
        assert result == ""

    def test_both_empty(self):
        """Both empty strings returns empty."""
        result = deduplicate_overlap("", "")
        assert result == ""

    def test_long_overlap_respects_max_window(self):
        """Overlap longer than max_overlap_words is not detected."""
        prev = " ".join([f"w{i}" for i in range(20)])
        new = " ".join([f"w{i}" for i in range(15, 25)])
        # Default max_overlap_words=10, overlap is 5 words (w15..w19)
        result = deduplicate_overlap(prev, new)
        assert result == " ".join([f"w{i}" for i in range(20, 25)])
