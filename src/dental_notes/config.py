"""Application configuration via pydantic-settings.

All settings can be overridden via environment variables prefixed with DENTAL_.
Example: DENTAL_WHISPER_MODEL=base overrides whisper_model.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dental-notes application settings.

    Defaults are tuned for GTX 1050 (4GB VRAM) with int8 quantization.
    Host defaults to 127.0.0.1 to ensure no network exposure (PRV-01).
    """

    model_config = SettingsConfigDict(env_prefix="DENTAL_")

    # Whisper model
    whisper_model: str = "small"
    compute_type: str = "int8"
    custom_vocab_path: Path = Path("vocab.txt")

    # Audio capture
    sample_rate: int = 16000

    # VAD
    vad_threshold: float = 0.5

    # Chunking
    max_chunk_duration_secs: int = 20
    silence_gap_secs: float = 1.5
    overlap_secs: float = 1.0

    # Storage
    storage_dir: Path = Path("transcripts")
    sessions_dir: Path = Path("sessions")

    # Server — 0.0.0.0 allows WSL→Windows browser access.
    # Patient data stays local (PRV-01) because the tool runs on LAN only.
    host: str = "0.0.0.0"
    port: int = 8000

    # Ollama LLM — all inference runs locally (PRV-01)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_fallback_model: str = "qwen3:4b"
    ollama_temperature: float = 0.0
    ollama_num_ctx: int = 8192
