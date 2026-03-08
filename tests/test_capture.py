"""Tests for AudioCapture boundary logic without real PortAudio.

Tests the queue-based producer-consumer pattern, RMS level calculation,
and device listing/matching -- all without opening a real audio stream.
"""

import math
from unittest.mock import patch

import numpy as np
import pytest

from dental_notes.audio.capture import (
    BLOCK_SIZE,
    AudioCapture,
    find_device_by_name,
    list_input_devices,
)
from dental_notes.config import Settings


@pytest.fixture
def capture(tmp_path):
    """AudioCapture instance with test settings (no real stream opened)."""
    settings = Settings(storage_dir=tmp_path / "transcripts")
    return AudioCapture(settings)


# --- Callback and queue tests ---


class TestAudioCallback:
    """AudioCapture._audio_callback enqueue behavior."""

    def test_audio_callback_enqueues_block(self, capture):
        """Calling _audio_callback with 2D indata puts a flattened 1D block on the queue."""
        rng = np.random.default_rng(0)
        indata = rng.random((BLOCK_SIZE, 1)).astype(np.float32)

        capture._audio_callback(indata, BLOCK_SIZE, None, None)

        assert capture.audio_q.qsize() == 1
        block = capture.audio_q.get_nowait()
        assert block.ndim == 1
        assert block.shape == (BLOCK_SIZE,)
        np.testing.assert_array_almost_equal(block, indata.flatten())

    def test_audio_callback_drops_when_queue_full(self, capture):
        """After filling queue to maxsize (200), additional blocks are silently dropped."""
        rng = np.random.default_rng(0)
        block_2d = rng.random((BLOCK_SIZE, 1)).astype(np.float32)

        # Fill the queue to capacity
        for _ in range(200):
            capture._audio_callback(block_2d, BLOCK_SIZE, None, None)

        assert capture.audio_q.qsize() == 200

        # One more should be silently dropped
        capture._audio_callback(block_2d, BLOCK_SIZE, None, None)
        assert capture.audio_q.qsize() == 200  # Still 200, not 201


class TestGetBlock:
    """AudioCapture.get_block retrieval behavior."""

    def test_get_block_returns_fifo(self, capture):
        """Blocks are retrieved in the order they were enqueued."""
        rng = np.random.default_rng(0)
        blocks = [rng.random((BLOCK_SIZE, 1)).astype(np.float32) for _ in range(3)]

        for b in blocks:
            capture._audio_callback(b, BLOCK_SIZE, None, None)

        for expected_2d in blocks:
            result = capture.get_block()
            assert result is not None
            np.testing.assert_array_almost_equal(result, expected_2d.flatten())

    def test_get_block_returns_none_when_empty(self, capture):
        """Returns None when queue is empty (within 100ms timeout)."""
        result = capture.get_block()
        assert result is None


class TestGetLevel:
    """AudioCapture.get_level RMS calculation."""

    def test_get_level_returns_zero_initially(self, capture):
        """Before any blocks, get_level() returns 0.0."""
        assert capture.get_level() == 0.0

    def test_get_level_returns_rms_of_last_block(self, capture):
        """After callback, get_level() returns correct RMS value."""
        rng = np.random.default_rng(42)
        indata = rng.random((BLOCK_SIZE, 1)).astype(np.float32)

        capture._audio_callback(indata, BLOCK_SIZE, None, None)

        # Compute expected RMS manually
        block = indata.flatten()
        expected_rms = math.sqrt(float(np.mean(block**2)))

        assert capture.get_level() == pytest.approx(expected_rms, rel=1e-6)


# --- Device listing tests ---


MOCK_DEVICES = [
    {"name": "Yeti Classic", "max_input_channels": 2, "max_output_channels": 0},
    {"name": "Speakers (Realtek)", "max_input_channels": 0, "max_output_channels": 2},
    {"name": "Blue Yeti Stereo", "max_input_channels": 2, "max_output_channels": 2},
    {"name": "HDMI Output", "max_input_channels": 0, "max_output_channels": 8},
    {"name": "USB Mic", "max_input_channels": 1, "max_output_channels": 0},
]


class TestListInputDevices:
    """list_input_devices filtering and shape."""

    @patch("dental_notes.audio.capture.sd.query_devices", return_value=MOCK_DEVICES)
    def test_list_input_devices_filters_inputs(self, mock_qd):
        """Only input devices (max_input_channels > 0) are returned."""
        devices = list_input_devices()
        # Yeti Classic (idx 0), Blue Yeti Stereo (idx 2), USB Mic (idx 4)
        assert len(devices) == 3
        names = [d["name"] for d in devices]
        assert "Speakers (Realtek)" not in names
        assert "HDMI Output" not in names

    @patch("dental_notes.audio.capture.sd.query_devices", return_value=MOCK_DEVICES)
    def test_list_input_devices_returns_correct_shape(self, mock_qd):
        """Each dict has index, name, channels keys."""
        devices = list_input_devices()
        for d in devices:
            assert "index" in d
            assert "name" in d
            assert "channels" in d
            assert isinstance(d["index"], int)
            assert isinstance(d["name"], str)
            assert isinstance(d["channels"], int)


class TestFindDeviceByName:
    """find_device_by_name matching behavior."""

    @patch("dental_notes.audio.capture.sd.query_devices", return_value=MOCK_DEVICES)
    def test_find_device_by_name_partial_match(self, mock_qd):
        """'Yeti' matches 'Yeti Classic' (case-insensitive)."""
        idx = find_device_by_name("yeti")
        assert idx == 0  # First matching input device

    @patch("dental_notes.audio.capture.sd.query_devices", return_value=MOCK_DEVICES)
    def test_find_device_by_name_returns_none_not_found(self, mock_qd):
        """Returns None for non-existent device name."""
        idx = find_device_by_name("Nonexistent Device XYZ")
        assert idx is None

    @patch("dental_notes.audio.capture.sd.query_devices", return_value=MOCK_DEVICES)
    def test_find_device_by_name_ignores_output_devices(self, mock_qd):
        """Output-only device matching by name returns None."""
        idx = find_device_by_name("HDMI Output")
        assert idx is None
