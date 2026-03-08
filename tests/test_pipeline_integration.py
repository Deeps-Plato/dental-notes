"""Full pipeline integration test: audio -> VAD -> chunker -> whisper -> transcript.

This is the centerpiece test for Phase 1.1 -- it catches the class of bugs that
killed v1 ("all units pass but the pipeline doesn't connect"). Uses REAL
components with only hardware boundaries faked:

REAL: VadDetector (with FakeVadModel), AudioChunker, TranscriptWriter,
      SessionManager, deduplicate_overlap, classify_speaker
FAKE: AudioCapture (no PortAudio), WhisperService (no GPU/CUDA),
      VadModel (no silero download)
"""

import time
from pathlib import Path

import numpy as np
import pytest

from dental_notes.audio.vad import VadDetector
from dental_notes.config import Settings
from dental_notes.session.manager import SessionManager
from tests.conftest import FakeAudioCapture, FakeVadModel, FakeWhisperService


@pytest.fixture
def integration_settings(tmp_path: Path) -> Settings:
    """Settings tuned for fast integration test.

    Short chunk duration ensures chunks finalize quickly without
    needing hundreds of audio blocks.
    """
    return Settings(
        storage_dir=tmp_path / "transcripts",
        max_chunk_duration_secs=1,  # 16000 samples = 10 blocks of 1600
        silence_gap_secs=0.2,  # 3200 samples = 2 blocks of silence
        overlap_secs=0.1,  # 1600 samples = 1 block overlap
    )


@pytest.fixture
def speech_blocks() -> list[np.ndarray]:
    """Audio blocks that simulate speech.

    12 blocks of 1600 float32 samples each (matching BLOCK_SIZE).
    Uses random data to simulate real audio variance.
    """
    rng = np.random.default_rng(seed=42)
    return [
        (rng.random(1600) * 0.5).astype(np.float32) for _ in range(12)
    ]


@pytest.fixture
def dental_whisper() -> FakeWhisperService:
    """FakeWhisperService returning dental appointment dialogue.

    Returns text with clear Doctor and Patient language so speaker
    classification can assign labels.
    """
    return FakeWhisperService(
        responses=[
            "The patient presents with pain on tooth 14",
            "I recommend a crown preparation",
            "Okay doctor that sounds good",
            "Let's schedule the crown prep for next week",
        ]
    )


@pytest.fixture
def pipeline_manager(
    integration_settings: Settings,
    speech_blocks: list[np.ndarray],
    dental_whisper: FakeWhisperService,
) -> SessionManager:
    """SessionManager wired with real components and fake hardware boundaries.

    Uses real VadDetector (with FakeVadModel), real AudioChunker,
    real TranscriptWriter, and fake AudioCapture/WhisperService.
    """
    # FakeVadModel needs enough probabilities for all sub-chunk calls.
    # Each 1600-sample block produces 3 sub-chunk calls (1600 / 512 = 3).
    # 12 blocks * 3 calls = 36 calls needed, plus extra for flush/overlap.
    vad_model = FakeVadModel(probabilities=[0.9] * 100)

    mgr = SessionManager(integration_settings)
    mgr._whisper = dental_whisper
    mgr._create_capture = lambda: FakeAudioCapture(speech_blocks)

    # Override chunker factory to use real AudioChunker with patched VadDetector
    def create_real_chunker_with_fake_model(vad: VadDetector):
        from dental_notes.transcription.chunker import AudioChunker

        # Replace the real silero-vad model with our fake
        vad._model = vad_model
        return AudioChunker(integration_settings, vad)

    mgr._create_chunker = create_real_chunker_with_fake_model

    return mgr


class TestPipelineIntegration:
    """Full pipeline integration tests proving end-to-end data flow."""

    def test_full_pipeline_produces_transcript_file(
        self, pipeline_manager: SessionManager, integration_settings: Settings
    ):
        """Start -> process -> stop produces a transcript file on disk.

        This is the critical assertion: the pipeline actually connects
        and produces output. Catches "units pass but pipeline doesn't
        connect" bugs.
        """
        pipeline_manager.start()
        time.sleep(1.5)
        transcript_path = pipeline_manager.stop()

        assert transcript_path.exists(), (
            f"Transcript file not created at {transcript_path}"
        )
        content = transcript_path.read_text()
        assert len(content) > 0, "Transcript file is empty"

    def test_pipeline_transcript_has_speaker_labels(
        self, pipeline_manager: SessionManager
    ):
        """Transcript file contains Doctor: or Patient: speaker labels.

        Proves speaker classification ran on transcribed text and was
        written to the transcript file by TranscriptWriter.
        """
        pipeline_manager.start()
        time.sleep(1.5)
        transcript_path = pipeline_manager.stop()

        content = transcript_path.read_text()
        has_doctor = "Doctor:" in content
        has_patient = "Patient:" in content
        assert has_doctor or has_patient, (
            f"No speaker labels found in transcript:\n{content}"
        )

    def test_pipeline_transcript_has_dental_content(
        self, pipeline_manager: SessionManager, dental_whisper: FakeWhisperService
    ):
        """Transcript contains the dental text FakeWhisperService returned.

        Proves data flowed through the chain: audio blocks reached
        WhisperService, which returned dental text, which was written
        to the file (not canned data bypassing the pipeline).
        """
        pipeline_manager.start()
        time.sleep(1.5)
        transcript_path = pipeline_manager.stop()

        content = transcript_path.read_text()
        # At least one of the dental responses should appear in the transcript
        dental_phrases = [r for r in dental_whisper._responses if r.strip()]
        found_any = any(phrase in content for phrase in dental_phrases)
        assert found_any, (
            f"No dental content found in transcript.\n"
            f"Expected one of: {dental_phrases}\n"
            f"Got: {content}"
        )

    def test_pipeline_no_audio_retained(
        self, pipeline_manager: SessionManager
    ):
        """After stop(), no large numpy arrays remain in SessionManager.

        Proves AUD-01 compliance: audio data is discarded after
        transcription, not stored in memory.
        """
        pipeline_manager.start()
        time.sleep(1.5)
        pipeline_manager.stop()

        for attr_name in dir(pipeline_manager):
            if attr_name.startswith("__"):
                continue
            try:
                val = getattr(pipeline_manager, attr_name)
            except Exception:
                continue
            if isinstance(val, np.ndarray) and val.size > 100:
                pytest.fail(
                    f"SessionManager retains large audio array "
                    f"in '{attr_name}' (size={val.size}) after stop"
                )

    def test_pipeline_whisper_received_audio_data(
        self, pipeline_manager: SessionManager, dental_whisper: FakeWhisperService
    ):
        """FakeWhisperService.transcribe_calls has entries after pipeline runs.

        Proves real audio data reached the transcription step through
        the pipeline (not canned data bypassing VAD/chunker).
        """
        pipeline_manager.start()
        time.sleep(1.5)
        pipeline_manager.stop()

        assert len(dental_whisper.transcribe_calls) >= 1, (
            "WhisperService.transcribe was never called -- "
            "audio data did not flow through the pipeline"
        )
        # Each transcribe call should receive a numpy array
        for i, call_data in enumerate(dental_whisper.transcribe_calls):
            assert isinstance(call_data, np.ndarray), (
                f"transcribe call {i} received {type(call_data)}, "
                f"expected np.ndarray"
            )
            assert call_data.size > 0, (
                f"transcribe call {i} received empty array"
            )
