"""Tests for HotkeyListener action routing without pynput/X display.

HotkeyListener uses lazy imports for pynput inside methods, so we mock
sys.modules to avoid importing the real pynput (which crashes on headless
Linux). Tests verify key routing, state-based action dispatch, and queue
processing.
"""

import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dental_notes.session.manager import SessionState

# --- Mock pynput setup ---


class _MockKey:
    """Stand-in for pynput.keyboard.Key with f8 and f9 attributes."""

    def __init__(self):
        self.f8 = SimpleNamespace(_name="f8")
        self.f9 = SimpleNamespace(_name="f9")
        self.f10 = SimpleNamespace(_name="f10")
        self.space = SimpleNamespace(_name="space")


MOCK_KEY = _MockKey()


def _install_mock_pynput():
    """Patch sys.modules so `from pynput.keyboard import Key` works without X."""
    mock_keyboard = SimpleNamespace(Key=MOCK_KEY)
    mock_pynput = SimpleNamespace(keyboard=mock_keyboard)
    return patch.dict(
        sys.modules,
        {"pynput": mock_pynput, "pynput.keyboard": mock_keyboard},
    )


@pytest.fixture
def listener(fake_session_manager):
    """HotkeyListener wired to FakeSessionManager, with mocked pynput."""
    from dental_notes.ui.hotkey import HotkeyListener

    return HotkeyListener(fake_session_manager)


# --- _process_actions tests (state-based routing) ---


def _run_actions(listener, actions, wait=0.3):
    """Start the worker thread, push actions, wait, then stop."""
    listener._running = True
    worker = threading.Thread(target=listener._process_actions, daemon=True)
    worker.start()
    for action in actions:
        listener._action_queue.put_nowait(action)
    time.sleep(wait)
    listener._running = False
    worker.join(timeout=2.0)


class TestToggleStartStop:
    """F9 toggle_start_stop action routing."""

    def test_toggle_start_stop_starts_idle_session(
        self, listener, fake_session_manager
    ):
        """When state is IDLE, toggle_start_stop transitions to RECORDING."""
        assert fake_session_manager.get_state() == SessionState.IDLE
        _run_actions(listener, ["toggle_start_stop"])
        assert fake_session_manager.get_state() == SessionState.RECORDING

    def test_toggle_start_stop_stops_recording_session(
        self, listener, fake_session_manager
    ):
        """When state is RECORDING, toggle_start_stop transitions to IDLE."""
        fake_session_manager.start()
        assert fake_session_manager.get_state() == SessionState.RECORDING
        _run_actions(listener, ["toggle_start_stop"])
        assert fake_session_manager.get_state() == SessionState.IDLE

    def test_toggle_start_stop_stops_paused_session(
        self, listener, fake_session_manager
    ):
        """When state is PAUSED, toggle_start_stop transitions to IDLE."""
        fake_session_manager.start()
        fake_session_manager.pause()
        assert fake_session_manager.get_state() == SessionState.PAUSED
        _run_actions(listener, ["toggle_start_stop"])
        assert fake_session_manager.get_state() == SessionState.IDLE


class TestTogglePauseResume:
    """F8 toggle_pause_resume action routing."""

    def test_toggle_pause_resume_pauses_recording(
        self, listener, fake_session_manager
    ):
        """When state is RECORDING, toggle_pause_resume transitions to PAUSED."""
        fake_session_manager.start()
        assert fake_session_manager.get_state() == SessionState.RECORDING
        _run_actions(listener, ["toggle_pause_resume"])
        assert fake_session_manager.get_state() == SessionState.PAUSED

    def test_toggle_pause_resume_resumes_paused(
        self, listener, fake_session_manager
    ):
        """When state is PAUSED, toggle_pause_resume transitions to RECORDING."""
        fake_session_manager.start()
        fake_session_manager.pause()
        assert fake_session_manager.get_state() == SessionState.PAUSED
        _run_actions(listener, ["toggle_pause_resume"])
        assert fake_session_manager.get_state() == SessionState.RECORDING

    def test_toggle_pause_resume_ignored_when_idle(
        self, listener, fake_session_manager
    ):
        """When state is IDLE, toggle_pause_resume does nothing (no error)."""
        assert fake_session_manager.get_state() == SessionState.IDLE
        _run_actions(listener, ["toggle_pause_resume"])
        assert fake_session_manager.get_state() == SessionState.IDLE


class TestActionQueue:
    """Queue processing handles multiple sequential actions."""

    def test_action_queue_processes_multiple_actions(
        self, listener, fake_session_manager
    ):
        """Queue multiple actions and verify they execute in order."""
        assert fake_session_manager.get_state() == SessionState.IDLE
        # Start -> Pause -> Resume -> Stop
        _run_actions(
            listener,
            [
                "toggle_start_stop",
                "toggle_pause_resume",
                "toggle_pause_resume",
                "toggle_start_stop",
            ],
            wait=0.5,
        )
        # Should end up IDLE after start -> pause -> resume -> stop
        assert fake_session_manager.get_state() == SessionState.IDLE


# --- _on_key_press tests (key routing to queue) ---


class TestOnKeyPress:
    """Key press routing to action queue."""

    def test_on_key_press_routes_f9_to_toggle(self, listener):
        """_on_key_press with F9 key puts 'toggle_start_stop' in queue."""
        with _install_mock_pynput():
            listener._on_key_press(MOCK_KEY.f9)

        assert listener._action_queue.qsize() == 1
        assert listener._action_queue.get_nowait() == "toggle_start_stop"

    def test_on_key_press_routes_f8_to_pause(self, listener):
        """_on_key_press with F8 key puts 'toggle_pause_resume' in queue."""
        with _install_mock_pynput():
            listener._on_key_press(MOCK_KEY.f8)

        assert listener._action_queue.qsize() == 1
        assert listener._action_queue.get_nowait() == "toggle_pause_resume"

    def test_on_key_press_ignores_other_keys(self, listener):
        """_on_key_press with other keys does not put anything in queue."""
        with _install_mock_pynput():
            listener._on_key_press(MOCK_KEY.f10)
            listener._on_key_press(MOCK_KEY.space)

        assert listener._action_queue.qsize() == 0
