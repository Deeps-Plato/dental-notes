"""Shared test fixtures and fakes for dental-notes v2.

All shared fakes (FakeAudioCapture, FakeWhisperService, FakeChunker,
FakeSessionManager, FakeOllamaService) live here so any test file can
use them via pytest auto-discovery.

Integration test infrastructure:
- --integration flag enables tests marked @pytest.mark.integration
- Integration tests connect to real Ollama at localhost:11434
- Model auto-detection: tries qwen3:8b, falls back to qwen3:4b
"""

import json
from pathlib import Path

import numpy as np
import pytest

from dental_notes.session.manager import SessionState


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --integration flag to enable integration tests."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests requiring real Ollama service",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless --integration flag is passed."""
    if config.getoption("--integration"):
        return
    skip_integration = pytest.mark.skip(
        reason="Need --integration flag to run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def test_settings(tmp_path: Path):
    """Settings with a tmp_path storage_dir for test isolation."""
    from dental_notes.config import Settings

    return Settings(storage_dir=tmp_path / "transcripts")


@pytest.fixture
def mock_audio_speech() -> np.ndarray:
    """1 second of speech-like audio: 440Hz sine wave at 16kHz sample rate."""
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def mock_audio_silence() -> np.ndarray:
    """1 second of silence: near-zero values at 16kHz sample rate."""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def mock_audio_noise() -> np.ndarray:
    """1 second of noise simulating dental drill: random values at 16kHz."""
    rng = np.random.default_rng(seed=42)
    return (rng.random(16000) * 0.1).astype(np.float32)


# --- Shared fake classes ---


class FakeVadModel:
    """Mock silero-vad model for testing without downloading the real model.

    Returns configurable speech probabilities for each call.
    """

    def __init__(self, probabilities: list[float] | None = None):
        self._probabilities = probabilities or []
        self._call_index = 0

    def __call__(self, audio_chunk, sample_rate: int) -> "FakeTensor":
        if self._call_index < len(self._probabilities):
            prob = self._probabilities[self._call_index]
            self._call_index += 1
        else:
            prob = 0.0
        return FakeTensor(prob)

    def reset_states(self) -> None:
        """Reset model state (mirrors silero-vad API)."""
        self._call_index = 0


class FakeTensor:
    """Minimal tensor-like object that supports .item()."""

    def __init__(self, value: float):
        self._value = value

    def item(self) -> float:
        return self._value


class FakeAudioCapture:
    """Fake AudioCapture that returns pre-loaded audio blocks."""

    def __init__(self, blocks: list[np.ndarray] | None = None):
        self._blocks = list(blocks or [])
        self._block_index = 0
        self._started = False
        self._stopped = False
        self._last_block: np.ndarray | None = None

    def start(self, device_index: int | None = None) -> None:
        self._started = True
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
        self._started = False

    def get_block(self) -> np.ndarray | None:
        if self._block_index < len(self._blocks):
            block = self._blocks[self._block_index]
            self._block_index += 1
            self._last_block = block
            return block
        return None

    def get_level(self) -> float:
        if self._last_block is None:
            return 0.0
        return float(np.sqrt(np.mean(self._last_block**2)))


class FakeWhisperService:
    """Fake WhisperService that returns configurable text."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or ["transcribed text"])
        self._call_index = 0
        self.transcribe_calls: list[np.ndarray] = []

    def transcribe(self, audio: np.ndarray) -> str:
        self.transcribe_calls.append(audio)
        if self._call_index < len(self._responses):
            text = self._responses[self._call_index]
            self._call_index += 1
            return text
        return ""

    @property
    def is_loaded(self) -> bool:
        return True

    def load_model(self) -> None:
        pass

    def unload(self) -> None:
        pass


class FakeChunker:
    """Fake AudioChunker that returns a chunk every N blocks."""

    def __init__(
        self, chunk_every: int = 3, chunk_data: np.ndarray | None = None
    ):
        self._chunk_every = chunk_every
        self._chunk_data = (
            chunk_data
            if chunk_data is not None
            else np.zeros(16000, dtype=np.float32)
        )
        self._feed_count = 0

    def feed(self, audio_block: np.ndarray) -> np.ndarray | None:
        self._feed_count += 1
        if self._feed_count % self._chunk_every == 0:
            return self._chunk_data
        return None

    def flush(self) -> np.ndarray | None:
        if self._feed_count > 0 and self._feed_count % self._chunk_every != 0:
            return self._chunk_data
        return None


class FakeSessionManager:
    """Mimics SessionManager state transitions and returns canned data."""

    def __init__(self):
        self._state = SessionState.IDLE
        self._chunks: list[tuple[str, str]] = []
        self._level = 0.0
        self._transcript_path = Path("/tmp/test-transcript.txt")

    def start(self, mic_device: int | None = None) -> None:
        if self._state != SessionState.IDLE:
            raise RuntimeError(
                f"Cannot start: state is {self._state.value}"
            )
        self._state = SessionState.RECORDING
        self._chunks = []

    def pause(self) -> None:
        if self._state != SessionState.RECORDING:
            raise RuntimeError(
                f"Cannot pause: state is {self._state.value}"
            )
        self._state = SessionState.PAUSED

    def resume(self) -> None:
        if self._state != SessionState.PAUSED:
            raise RuntimeError(
                f"Cannot resume: state is {self._state.value}"
            )
        self._state = SessionState.RECORDING

    def stop(self) -> Path:
        if self._state not in (SessionState.RECORDING, SessionState.PAUSED):
            raise RuntimeError(
                f"Cannot stop: state is {self._state.value}"
            )
        self._state = SessionState.IDLE
        return self._transcript_path

    def get_transcript(self) -> str:
        return "\n\n".join(f"{s}: {t}" for s, t in self._chunks)

    def get_chunks(self, start: int = 0) -> list[tuple[str, str]]:
        return self._chunks[start:]

    def get_chunk_count(self) -> int:
        return len(self._chunks)

    def get_state(self) -> SessionState:
        return self._state

    def is_active(self) -> bool:
        return self._state in (SessionState.RECORDING, SessionState.PAUSED)

    def get_level(self) -> float:
        return self._level


# --- Shared fixtures ---


@pytest.fixture
def fake_vad_speech() -> FakeVadModel:
    """FakeVadModel that always returns high speech probability."""
    return FakeVadModel(probabilities=[0.9] * 100)


@pytest.fixture
def fake_vad_silence() -> FakeVadModel:
    """FakeVadModel that always returns low speech probability."""
    return FakeVadModel(probabilities=[0.1] * 100)


@pytest.fixture
def fake_session_manager() -> FakeSessionManager:
    """FakeSessionManager for route/hotkey tests."""
    return FakeSessionManager()


@pytest.fixture
def audio_blocks() -> list[np.ndarray]:
    """Pre-loaded audio blocks for testing (9 blocks of 1600 samples)."""
    return [
        np.random.default_rng(i).random(1600).astype(np.float32)
        for i in range(9)
    ]


class FakeOllamaService:
    """Fake OllamaService for unit tests -- returns canned response, records calls.

    Default response_data matches ExtractionResult schema with cdt_codes
    nested inside soap_note (not at top level).
    """

    def __init__(self, response_data: dict | None = None):
        self.response_data = response_data or {
            "soap_note": {
                "subjective": (
                    "Patient reports sensitivity to cold on upper right "
                    "tooth for one week."
                ),
                "objective": (
                    "Tooth #14 mesial-occlusal discoloration. "
                    "Probing depths 2-3mm within normal limits."
                ),
                "assessment": "Class II caries on #14 mesial-occlusal surface.",
                "plan": (
                    "Two-surface composite restoration on #14. "
                    "Periapical radiograph to rule out periapical pathology."
                ),
                "cdt_codes": [
                    {
                        "code": "D2392",
                        "description": (
                            "Resin-based composite - two surfaces, posterior"
                        ),
                    },
                    {
                        "code": "D0220",
                        "description": "Periapical radiograph",
                    },
                ],
                "clinical_discussion": [
                    "Explained Class II caries as decay between teeth "
                    "requiring two-surface restoration",
                    "Composite chosen over amalgam for aesthetics and "
                    "tooth-conserving bonding",
                    "Periapical radiograph to rule out nerve involvement "
                    "before restoration",
                ],
            },
            "speaker_chunks": [
                {
                    "chunk_id": 0,
                    "speaker": "Doctor",
                    "text": "Good morning, how are you today?",
                },
                {
                    "chunk_id": 1,
                    "speaker": "Patient",
                    "text": (
                        "My upper right tooth has been sensitive to cold."
                    ),
                },
            ],
            "clinical_summary": (
                "Patient presents with cold sensitivity on #14. "
                "Class II caries diagnosed. "
                "Plan for two-surface composite restoration."
            ),
        }
        self.last_system_prompt: str | None = None
        self.last_user_content: str | None = None
        self.call_count: int = 0
        self.unload_count: int = 0

    def is_available(self) -> bool:
        return True

    def is_model_ready(self) -> bool:
        return True

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        schema: dict,
        **kwargs,
    ) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_content = user_content
        self.call_count += 1
        return json.dumps(self.response_data)

    def unload(self) -> None:
        self.unload_count += 1


@pytest.fixture
def fake_ollama_service() -> FakeOllamaService:
    """FakeOllamaService for clinical extraction tests."""
    return FakeOllamaService()


# --- GPU handoff fakes ---


class FakeWhisperServiceGpu:
    """Fake WhisperService with call tracking for GPU handoff tests.

    Unlike FakeWhisperService (which tracks transcription calls),
    this tracks unload/load_model calls for verifying GPU memory
    management sequences.
    """

    def __init__(self) -> None:
        self.unload_count: int = 0
        self.load_model_count: int = 0
        self._is_loaded: bool = True

    def unload(self) -> None:
        self.unload_count += 1
        self._is_loaded = False

    def load_model(self) -> None:
        self.load_model_count += 1
        self._is_loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded


@pytest.fixture
def fake_whisper_service() -> FakeWhisperServiceGpu:
    """FakeWhisperServiceGpu for GPU handoff tests."""
    return FakeWhisperServiceGpu()


# --- Sample transcript data ---


SAMPLE_DENTAL_TRANSCRIPT = """Doctor: Good morning, how are you today?

Patient: I'm doing well, thanks. My upper right tooth has been really sensitive to cold for the past week.

Doctor: Let's take a look. Open wide please. I can see some discoloration on tooth number 14, the mesial-occlusal surface. Let me probe around... pocket depths are normal, 2 to 3 millimeters.

Patient: Is it a cavity?

Doctor: Yes, I'm seeing a Class II caries on number 14, mesial-occlusal. Think of it like a pothole forming between the teeth. Right now it's still in the outer shell, the enamel and into the dentin, but it hasn't reached the nerve yet. That's good news because we can fix it with a filling instead of needing a root canal.

Patient: Oh okay, so what kind of filling?

Doctor: I'd recommend a composite, which is a tooth-colored resin material. The alternative would be an amalgam, the silver-colored filling, but composite bonds directly to the tooth structure so we can be more conservative and preserve more of your natural tooth. It also looks much better. The downside is composite can be slightly more sensitive to technique, but for a two-surface restoration like this, it's the standard of care.

Patient: What happens if I don't do it?

Doctor: Good question. If we leave it, the decay will keep progressing deeper. Eventually it'll reach the nerve, and then we're looking at either a root canal or potentially losing the tooth. Catching it now means a straightforward filling. Much simpler and less expensive than waiting.

Patient: Okay, sounds good. Will insurance cover it?

Doctor: It should be covered under your plan. We'll schedule you for the restoration. I'll also want to take a periapical radiograph to rule out any periapical pathology before we start."""


@pytest.fixture
def sample_transcript() -> str:
    """Sample dental appointment transcript for extraction tests."""
    return SAMPLE_DENTAL_TRANSCRIPT


# --- Integration test fixtures (require real Ollama) ---


SAMPLE_CHUNKS: list[tuple[str, str]] = [
    ("Doctor", "Good morning, how are you today?"),
    (
        "Patient",
        "I'm doing well, thanks. My upper right tooth has been "
        "really sensitive to cold for the past week.",
    ),
    (
        "Doctor",
        "Let's take a look. Open wide please. I can see some "
        "discoloration on tooth number 14, the mesial-occlusal "
        "surface. Let me probe around... pocket depths are normal, "
        "2 to 3 millimeters.",
    ),
    ("Patient", "Is it a cavity?"),
    (
        "Doctor",
        "Yes, I'm seeing a Class II caries on number 14, "
        "mesial-occlusal. Think of it like a pothole forming between "
        "the teeth. Right now it's still in the outer shell, the "
        "enamel and into the dentin, but it hasn't reached the nerve "
        "yet. That's good news because we can fix it with a filling "
        "instead of needing a root canal.",
    ),
    ("Patient", "Oh okay, so what kind of filling?"),
    (
        "Doctor",
        "I'd recommend a composite, which is a tooth-colored resin "
        "material. The alternative would be an amalgam, the silver-"
        "colored filling, but composite bonds directly to the tooth "
        "structure so we can be more conservative and preserve more "
        "of your natural tooth. It also looks much better. The "
        "downside is composite can be slightly more sensitive to "
        "technique, but for a two-surface restoration like this, "
        "it's the standard of care.",
    ),
    ("Patient", "What happens if I don't do it?"),
    (
        "Doctor",
        "Good question. If we leave it, the decay will keep "
        "progressing deeper. Eventually it'll reach the nerve, "
        "and then we're looking at either a root canal or "
        "potentially losing the tooth. Catching it now means a "
        "straightforward filling. Much simpler and less expensive "
        "than waiting.",
    ),
    ("Patient", "Okay, sounds good. Will insurance cover it?"),
    (
        "Doctor",
        "It should be covered under your plan. We'll schedule you "
        "for the restoration. I'll also want to take a periapical "
        "radiograph to rule out any periapical pathology before "
        "we start.",
    ),
]


@pytest.fixture
def sample_chunks() -> list[tuple[str, str]]:
    """Sample (speaker, text) chunks parsed from SAMPLE_DENTAL_TRANSCRIPT."""
    return SAMPLE_CHUNKS


@pytest.fixture
def integration_ollama_service(test_settings):
    """Real OllamaService for integration tests.

    Auto-detects model: tries qwen3:8b first, falls back to qwen3:4b.
    Skips test if Ollama is not available or no model is ready.
    """
    from dental_notes.clinical.ollama_service import OllamaService

    service = OllamaService(
        host=test_settings.ollama_host,
        model=test_settings.ollama_model,
    )
    if not service.is_available():
        pytest.skip("Ollama not available at localhost:11434")

    if service.is_model_ready():
        return service

    # Try fallback model
    fallback = OllamaService(
        host=test_settings.ollama_host,
        model=test_settings.ollama_fallback_model,
    )
    if fallback.is_model_ready():
        return fallback

    pytest.skip(
        f"Neither {test_settings.ollama_model} nor "
        f"{test_settings.ollama_fallback_model} available"
    )


@pytest.fixture
def integration_extractor(integration_ollama_service, test_settings):
    """ClinicalExtractor connected to real Ollama for integration tests."""
    from dental_notes.clinical.extractor import ClinicalExtractor

    return ClinicalExtractor(integration_ollama_service, test_settings)


@pytest.fixture
def integration_reattributor(integration_ollama_service, test_settings):
    """SpeakerReattributor connected to real Ollama for integration tests."""
    from dental_notes.clinical.speaker import SpeakerReattributor

    return SpeakerReattributor(integration_ollama_service, test_settings)
