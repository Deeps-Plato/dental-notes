"""Tests for dental_notes.config.Settings defaults and env override."""

import pytest


def test_settings_loads_defaults():
    """Settings loads with correct defaults when no .env file exists."""
    from dental_notes.config import Settings

    s = Settings()
    assert s.whisper_model == "small"
    assert s.compute_type == "int8"
    assert s.sample_rate == 16000
    assert s.vad_threshold == 0.5
    assert s.max_chunk_duration_secs == 20
    assert s.silence_gap_secs == 1.5
    assert s.overlap_secs == 1.0
    assert str(s.storage_dir) == "transcripts"
    assert s.host == "0.0.0.0"
    assert s.port == 8000


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch):
    """Settings values can be overridden via DENTAL_ prefixed env vars."""
    monkeypatch.setenv("DENTAL_WHISPER_MODEL", "base")
    monkeypatch.setenv("DENTAL_COMPUTE_TYPE", "float16")
    monkeypatch.setenv("DENTAL_SAMPLE_RATE", "8000")
    monkeypatch.setenv("DENTAL_VAD_THRESHOLD", "0.7")
    monkeypatch.setenv("DENTAL_HOST", "192.168.1.1")
    monkeypatch.setenv("DENTAL_PORT", "9000")

    from dental_notes.config import Settings

    s = Settings()
    assert s.whisper_model == "base"
    assert s.compute_type == "float16"
    assert s.sample_rate == 8000
    assert s.vad_threshold == 0.7
    assert s.host == "192.168.1.1"
    assert s.port == 9000


def test_settings_host_default_binds_all():
    """Host defaults to 0.0.0.0 so WSL is reachable from Windows browser."""
    from dental_notes.config import Settings

    s = Settings()
    assert s.host == "0.0.0.0"


def test_settings_storage_dir_is_path():
    """storage_dir is a Path object."""
    from pathlib import Path

    from dental_notes.config import Settings

    s = Settings()
    assert isinstance(s.storage_dir, Path)


# --- Phase 5 config extensions ---


class TestPhase5ConfigSettings:
    """Phase 5 config fields: auto-pause, rolling buffer, auto-save, retry."""

    def test_auto_pause_silence_secs_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.auto_pause_silence_secs == 60.0

    def test_rolling_buffer_secs_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.rolling_buffer_secs == 10.0

    def test_auto_pause_enabled_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.auto_pause_enabled is True

    def test_auto_save_interval_secs_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.auto_save_interval_secs == 30.0

    def test_auto_save_chunk_threshold_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.auto_save_chunk_threshold == 5

    def test_extraction_max_retries_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.extraction_max_retries == 3

    def test_extraction_retry_base_delay_default(self):
        from dental_notes.config import Settings

        s = Settings()
        assert s.extraction_retry_base_delay == 2.0

    def test_phase5_fields_env_override(self, monkeypatch: pytest.MonkeyPatch):
        """Phase 5 fields can be overridden via DENTAL_ env vars."""
        monkeypatch.setenv("DENTAL_AUTO_PAUSE_SILENCE_SECS", "120.0")
        monkeypatch.setenv("DENTAL_ROLLING_BUFFER_SECS", "15.0")
        monkeypatch.setenv("DENTAL_AUTO_PAUSE_ENABLED", "false")
        monkeypatch.setenv("DENTAL_AUTO_SAVE_INTERVAL_SECS", "60.0")
        monkeypatch.setenv("DENTAL_AUTO_SAVE_CHUNK_THRESHOLD", "10")
        monkeypatch.setenv("DENTAL_EXTRACTION_MAX_RETRIES", "5")
        monkeypatch.setenv("DENTAL_EXTRACTION_RETRY_BASE_DELAY", "3.0")

        from dental_notes.config import Settings

        s = Settings()
        assert s.auto_pause_silence_secs == 120.0
        assert s.rolling_buffer_secs == 15.0
        assert s.auto_pause_enabled is False
        assert s.auto_save_interval_secs == 60.0
        assert s.auto_save_chunk_threshold == 10
        assert s.extraction_max_retries == 5
        assert s.extraction_retry_base_delay == 3.0
