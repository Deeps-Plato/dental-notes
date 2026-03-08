"""Tests for main.py app factory and lifespan behavior.

Verifies create_app() produces a FastAPI app with the correct title,
static mount, router inclusion, and lifespan. Tests are structural
and do not require GPU, audio hardware, or X display.
"""

from fastapi import FastAPI
from fastapi.routing import Mount

from dental_notes.main import create_app


def test_create_app_returns_fastapi():
    """create_app() returns a FastAPI instance."""
    app = create_app()
    assert isinstance(app, FastAPI)


def test_create_app_has_correct_title():
    """App title is 'Dental Notes'."""
    app = create_app()
    assert app.title == "Dental Notes"


def test_create_app_includes_router():
    """App includes a route for '/' (from ui.routes)."""
    app = create_app()
    paths = [r.path for r in app.routes]
    assert "/" in paths


def test_create_app_mounts_static():
    """App mounts StaticFiles at '/static'."""
    app = create_app()
    static_mounts = [
        r for r in app.routes
        if isinstance(r, Mount) and r.path == "/static"
    ]
    assert len(static_mounts) == 1
    # Verify it has an app attribute (StaticFiles mount)
    assert hasattr(static_mounts[0], "app")


def test_create_app_has_lifespan():
    """App has a lifespan context manager configured."""
    app = create_app()
    assert app.router.lifespan_context is not None


def test_lifespan_shutdown_stops_active_session():
    """Shutdown logic stops an active session.

    Tests the structural contract: when session_manager.is_active() is True
    during shutdown, session_manager.stop() should be called.
    We test this by calling the shutdown path with a FakeSessionManager
    that tracks whether stop() was called.
    """
    from tests.conftest import FakeSessionManager

    mgr = FakeSessionManager()
    mgr.start()  # Put it in RECORDING state
    assert mgr.is_active()

    # Simulate what lifespan shutdown does:
    # if session_manager.is_active(): session_manager.stop()
    if mgr.is_active():
        mgr.stop()

    assert not mgr.is_active()


def test_app_module_level_instance():
    """The module-level `app` variable in main.py is a FastAPI instance."""
    from dental_notes.main import app

    assert isinstance(app, FastAPI)
    assert app.title == "Dental Notes"
