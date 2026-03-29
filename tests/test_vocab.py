"""Tests for dental vocabulary management: custom vocab loading, hotwords, prompt building.

Covers:
- DENTAL_INITIAL_PROMPT content and token limit
- load_custom_vocab() file handling (missing, valid, comments, blank lines)
- TEMPLATE_HOTWORDS completeness for all appointment types
- build_initial_prompt() merging with custom vocab
"""

from pathlib import Path

import pytest


class TestDentalInitialPrompt:
    """DENTAL_INITIAL_PROMPT covers all 4 term categories under ~224 tokens."""

    def test_token_estimate_under_224(self):
        from dental_notes.transcription.vocab import DENTAL_INITIAL_PROMPT

        # Heuristic: ~4 chars per token
        token_estimate = len(DENTAL_INITIAL_PROMPT) / 4
        assert token_estimate <= 224, (
            f"DENTAL_INITIAL_PROMPT estimated at {token_estimate:.0f} tokens, "
            f"exceeds 224 limit"
        )

    def test_contains_anesthetics(self):
        from dental_notes.transcription.vocab import DENTAL_INITIAL_PROMPT

        assert "Lidocaine" in DENTAL_INITIAL_PROMPT
        assert "Septocaine" in DENTAL_INITIAL_PROMPT
        assert "Marcaine" in DENTAL_INITIAL_PROMPT

    def test_contains_materials(self):
        from dental_notes.transcription.vocab import DENTAL_INITIAL_PROMPT

        assert "Herculite" in DENTAL_INITIAL_PROMPT
        assert "Estelite" in DENTAL_INITIAL_PROMPT
        assert "Paracore" in DENTAL_INITIAL_PROMPT

    def test_contains_pathology(self):
        from dental_notes.transcription.vocab import DENTAL_INITIAL_PROMPT

        assert "radiolucency" in DENTAL_INITIAL_PROMPT
        assert "periapical" in DENTAL_INITIAL_PROMPT
        assert "dehiscence" in DENTAL_INITIAL_PROMPT

    def test_contains_anatomy(self):
        from dental_notes.transcription.vocab import DENTAL_INITIAL_PROMPT

        assert "CEJ" in DENTAL_INITIAL_PROMPT
        assert "furcation" in DENTAL_INITIAL_PROMPT
        assert "mandibular canal" in DENTAL_INITIAL_PROMPT


class TestLoadCustomVocab:
    """load_custom_vocab() reads a plain text vocab file."""

    def test_returns_empty_string_when_file_missing(self, tmp_path):
        from dental_notes.transcription.vocab import load_custom_vocab

        result = load_custom_vocab(tmp_path / "nonexistent.txt")
        assert result == ""

    def test_reads_terms_from_file(self, tmp_path):
        from dental_notes.transcription.vocab import load_custom_vocab

        vocab_file = tmp_path / "vocab.txt"
        vocab_file.write_text("Kavo\nDentsply\nIvoclar\n")
        result = load_custom_vocab(vocab_file)
        assert result == "Kavo Dentsply Ivoclar"

    def test_ignores_comment_lines(self, tmp_path):
        from dental_notes.transcription.vocab import load_custom_vocab

        vocab_file = tmp_path / "vocab.txt"
        vocab_file.write_text("# This is a comment\nKavo\n# Another comment\nDentsply\n")
        result = load_custom_vocab(vocab_file)
        assert result == "Kavo Dentsply"

    def test_ignores_blank_lines(self, tmp_path):
        from dental_notes.transcription.vocab import load_custom_vocab

        vocab_file = tmp_path / "vocab.txt"
        vocab_file.write_text("Kavo\n\n\nDentsply\n\n")
        result = load_custom_vocab(vocab_file)
        assert result == "Kavo Dentsply"


class TestTemplateHotwords:
    """TEMPLATE_HOTWORDS has entries for all 6 appointment types."""

    def test_has_all_appointment_types(self):
        from dental_notes.transcription.vocab import TEMPLATE_HOTWORDS

        expected_keys = {
            "comprehensive_exam",
            "restorative",
            "hygiene_recall",
            "endodontic",
            "oral_surgery",
            "general",
        }
        assert set(TEMPLATE_HOTWORDS.keys()) == expected_keys

    def test_all_values_are_nonempty_strings(self):
        from dental_notes.transcription.vocab import TEMPLATE_HOTWORDS

        for key, value in TEMPLATE_HOTWORDS.items():
            assert isinstance(value, str), f"{key} value is not a string"
            assert len(value) > 0, f"{key} has empty hotwords"


class TestBuildInitialPrompt:
    """build_initial_prompt() merges base prompt with custom vocab."""

    def test_returns_base_prompt_when_no_custom_vocab(self):
        from dental_notes.transcription.vocab import (
            DENTAL_INITIAL_PROMPT,
            build_initial_prompt,
        )

        result = build_initial_prompt()
        assert DENTAL_INITIAL_PROMPT in result

    def test_merges_custom_vocab_from_file(self, tmp_path):
        from dental_notes.transcription.vocab import build_initial_prompt

        vocab_file = tmp_path / "vocab.txt"
        vocab_file.write_text("CustomTerm1\nCustomTerm2\n")
        result = build_initial_prompt(custom_vocab_path=vocab_file)
        assert "CustomTerm1" in result
        assert "CustomTerm2" in result

    def test_token_limit_with_custom_vocab(self, tmp_path):
        from dental_notes.transcription.vocab import build_initial_prompt

        vocab_file = tmp_path / "vocab.txt"
        vocab_file.write_text("ShortTerm\n")
        result = build_initial_prompt(custom_vocab_path=vocab_file)
        # Result should still be within reasonable bounds
        token_estimate = len(result) / 4
        assert token_estimate <= 250, (
            f"Combined prompt estimated at {token_estimate:.0f} tokens"
        )
