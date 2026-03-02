"""Application configuration loaded from environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Auth
    dental_api_key: str

    # Anthropic
    anthropic_api_key: str

    # Whisper
    whisper_model_size: str = "base"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8765

    # Logging
    log_level: str = "INFO"


# Module-level singleton — instantiated once at import time.
settings = Settings()  # type: ignore[call-arg]
