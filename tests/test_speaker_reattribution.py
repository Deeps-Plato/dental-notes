"""Tests for SpeakerReattributor -- LLM-based speaker label correction.

Covers reattribute() including chunk count preservation, text preservation,
speaker label validation, empty input handling, and error cases.
Uses FakeOllamaService from conftest.py -- no real Ollama needed.
"""

import json

import pytest

from dental_notes.clinical.models import SpeakerChunk
from dental_notes.clinical.speaker import SpeakerReattributor
from dental_notes.config import Settings
from tests.conftest import FakeOllamaService


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Settings for speaker reattribution tests."""
    return Settings(storage_dir=tmp_path / "transcripts")


SAMPLE_CHUNKS = [
    ("Speaker_0", "Good morning, how are you today?"),
    ("Speaker_1", "I'm doing well. My tooth has been sensitive."),
    ("Speaker_0", "Let me take a look at tooth number 14."),
    ("Speaker_1", "Is it a cavity?"),
    ("Speaker_0", "Yes, Class II caries. We'll need a composite."),
]


def _make_speaker_ollama(
    chunks: list[tuple[str, str]],
    speakers: list[str] | None = None,
) -> FakeOllamaService:
    """Create FakeOllamaService returning speaker chunk data for reattribution.

    By default alternates Doctor/Patient. Pass explicit speakers list to override.
    """
    if speakers is None:
        speakers = [
            "Doctor" if i % 2 == 0 else "Patient"
            for i in range(len(chunks))
        ]
    response_data = {
        "chunks": [
            {
                "chunk_id": i,
                "speaker": speakers[i],
                "text": text,
            }
            for i, (_, text) in enumerate(chunks)
        ]
    }
    return FakeOllamaService(response_data=response_data)


@pytest.fixture
def speaker_ollama() -> FakeOllamaService:
    """FakeOllamaService configured for speaker reattribution."""
    return _make_speaker_ollama(SAMPLE_CHUNKS)


@pytest.fixture
def reattributor(
    speaker_ollama: FakeOllamaService, settings: Settings
) -> SpeakerReattributor:
    """SpeakerReattributor with fake ollama returning correct chunk count."""
    return SpeakerReattributor(speaker_ollama, settings)


class TestReattribute:
    """Tests for SpeakerReattributor.reattribute()."""

    def test_reattribute_returns_speaker_chunks(
        self, reattributor: SpeakerReattributor
    ) -> None:
        """reattribute() returns a list of SpeakerChunk objects."""
        result = reattributor.reattribute(SAMPLE_CHUNKS)
        assert isinstance(result, list)
        assert all(isinstance(c, SpeakerChunk) for c in result)

    def test_reattribute_preserves_chunk_count(
        self, reattributor: SpeakerReattributor
    ) -> None:
        """Output has same number of chunks as input."""
        result = reattributor.reattribute(SAMPLE_CHUNKS)
        assert len(result) == len(SAMPLE_CHUNKS)

    def test_reattribute_preserves_text(
        self, reattributor: SpeakerReattributor
    ) -> None:
        """Each output chunk.text matches input text."""
        result = reattributor.reattribute(SAMPLE_CHUNKS)
        for i, chunk in enumerate(result):
            assert chunk.text == SAMPLE_CHUNKS[i][1]

    def test_reattribute_assigns_valid_speakers(
        self, reattributor: SpeakerReattributor
    ) -> None:
        """Each chunk.speaker is 'Doctor', 'Patient', or 'Assistant'."""
        result = reattributor.reattribute(SAMPLE_CHUNKS)
        for chunk in result:
            assert chunk.speaker in ("Doctor", "Patient", "Assistant"), (
                f"Invalid speaker: {chunk.speaker}"
            )

    def test_reattribute_chunk_ids_sequential(
        self, reattributor: SpeakerReattributor
    ) -> None:
        """chunk_ids are 0, 1, 2, ... in order."""
        result = reattributor.reattribute(SAMPLE_CHUNKS)
        for i, chunk in enumerate(result):
            assert chunk.chunk_id == i

    def test_reattribute_empty_chunks_returns_empty(
        self, speaker_ollama: FakeOllamaService, settings: Settings
    ) -> None:
        """Empty input returns empty list without calling LLM."""
        reattr = SpeakerReattributor(speaker_ollama, settings)
        result = reattr.reattribute([])
        assert result == []
        assert speaker_ollama.call_count == 0

    def test_reattribute_passes_formatted_chunks(
        self,
        reattributor: SpeakerReattributor,
        speaker_ollama: FakeOllamaService,
    ) -> None:
        """LLM receives formatted chunks with indices and text."""
        reattributor.reattribute(SAMPLE_CHUNKS)
        content = speaker_ollama.last_user_content
        assert content is not None
        assert "[0]" in content
        assert "[1]" in content
        assert "Good morning" in content
        assert "sensitive" in content

    def test_reattribute_invalid_json_raises_value_error(
        self, settings: Settings
    ) -> None:
        """Invalid JSON from LLM raises ValueError."""

        class BadJsonOllama(FakeOllamaService):
            def generate_structured(self, *args, **kwargs):
                self.call_count += 1
                return "this is not json"

        reattr = SpeakerReattributor(BadJsonOllama(), settings)
        with pytest.raises(ValueError, match="invalid"):
            reattr.reattribute(SAMPLE_CHUNKS)

    def test_reattribute_wrong_chunk_count_raises_value_error(
        self, settings: Settings
    ) -> None:
        """LLM returning fewer chunks than input raises ValueError."""
        # Return only 2 chunks when 5 are expected
        short_response = {
            "chunks": [
                {"chunk_id": 0, "speaker": "Doctor", "text": "Hello"},
                {"chunk_id": 1, "speaker": "Patient", "text": "Hi"},
            ]
        }
        short_ollama = FakeOllamaService(response_data=short_response)
        reattr = SpeakerReattributor(short_ollama, settings)
        with pytest.raises(ValueError, match="chunk count"):
            reattr.reattribute(SAMPLE_CHUNKS)


class TestSpeakerSystemPrompt:
    """SPEAKER_SYSTEM_PROMPT describes 3 roles for LLM re-attribution."""

    def test_prompt_mentions_assistant_role(self) -> None:
        from dental_notes.clinical.speaker import SPEAKER_SYSTEM_PROMPT

        assert "Assistant" in SPEAKER_SYSTEM_PROMPT

    def test_prompt_contains_all_three_roles(self) -> None:
        from dental_notes.clinical.speaker import SPEAKER_SYSTEM_PROMPT

        assert "DOCTOR" in SPEAKER_SYSTEM_PROMPT or "Doctor" in SPEAKER_SYSTEM_PROMPT
        assert "PATIENT" in SPEAKER_SYSTEM_PROMPT or "Patient" in SPEAKER_SYSTEM_PROMPT
        assert "ASSISTANT" in SPEAKER_SYSTEM_PROMPT or "Assistant" in SPEAKER_SYSTEM_PROMPT

    def test_prompt_describes_assistant_behavior(self) -> None:
        from dental_notes.clinical.speaker import SPEAKER_SYSTEM_PROMPT

        # Should describe what makes someone an assistant
        prompt_lower = SPEAKER_SYSTEM_PROMPT.lower()
        assert "instrument" in prompt_lower or "supply" in prompt_lower
        assert "comfort" in prompt_lower or "charting" in prompt_lower
