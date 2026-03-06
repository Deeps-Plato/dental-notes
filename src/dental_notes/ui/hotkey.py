"""Keyboard shortcut listener for session control.

F9 toggles start/stop. F8 toggles pause/resume.

Callbacks are non-blocking -- they post actions to a queue, and a
separate daemon thread processes them. This avoids blocking the
Windows keyboard hook (pynput pitfall from research).

pynput is imported inside methods (not at module level) so tests
don't fail on headless Linux without X display.
"""

import logging
import queue
import threading

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for global keyboard shortcuts and triggers session actions.

    F9: Toggle start/stop (IDLE -> start, RECORDING/PAUSED -> stop)
    F8: Toggle pause/resume (RECORDING -> pause, PAUSED -> resume)

    All actions are processed in a background thread to avoid blocking
    the pynput keyboard hook callback.
    """

    def __init__(self, session_manager) -> None:
        self._session_manager = session_manager
        self._action_queue: queue.Queue[str] = queue.Queue()
        self._listener = None
        self._worker_thread: threading.Thread | None = None
        self._running = False

    def _on_key_press(self, key) -> None:
        """Handle key press events. Posts actions to queue (non-blocking)."""
        try:
            from pynput.keyboard import Key

            if key == Key.f9:
                self._action_queue.put_nowait("toggle_start_stop")
            elif key == Key.f8:
                self._action_queue.put_nowait("toggle_pause_resume")
        except Exception:
            pass  # Ignore any errors in the callback

    def _process_actions(self) -> None:
        """Worker thread: process queued hotkey actions."""
        from dental_notes.session.manager import SessionState

        while self._running:
            try:
                action = self._action_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                state = self._session_manager.get_state()

                if action == "toggle_start_stop":
                    if state == SessionState.IDLE:
                        self._session_manager.start()
                        logger.info("Hotkey F9: session started")
                    elif state in (SessionState.RECORDING, SessionState.PAUSED):
                        self._session_manager.stop()
                        logger.info("Hotkey F9: session stopped")

                elif action == "toggle_pause_resume":
                    if state == SessionState.RECORDING:
                        self._session_manager.pause()
                        logger.info("Hotkey F8: session paused")
                    elif state == SessionState.PAUSED:
                        self._session_manager.resume()
                        logger.info("Hotkey F8: session resumed")

            except Exception:
                logger.warning("Hotkey action failed", exc_info=True)

    def start(self) -> None:
        """Start the keyboard listener and action worker in daemon threads."""
        from pynput.keyboard import Listener

        self._running = True

        # Start action processor thread
        self._worker_thread = threading.Thread(
            target=self._process_actions,
            daemon=True,
            name="hotkey-worker",
        )
        self._worker_thread.start()

        # Start pynput listener
        self._listener = Listener(on_press=self._on_key_press)
        self._listener.daemon = True
        self._listener.start()

        logger.info("Hotkey listener started (F9=start/stop, F8=pause/resume)")

    def stop(self) -> None:
        """Stop the keyboard listener and action worker."""
        self._running = False

        if self._listener is not None:
            self._listener.stop()
            self._listener = None

        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None

        logger.info("Hotkey listener stopped")
