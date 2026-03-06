"""Tests for dental_notes.config.Settings defaults and env override."""

import os

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
    assert s.host == "127.0.0.1"
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


def test_settings_host_default_is_localhost():
    """PRV-01: host defaults to 127.0.0.1 (never 0.0.0.0)."""
    from dental_notes.config import Settings

    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.host != "0.0.0.0"


def test_settings_storage_dir_is_path():
    """storage_dir is a Path object."""
    from pathlib import Path

    from dental_notes.config import Settings

    s = Settings()
    assert isinstance(s.storage_dir, Path)
