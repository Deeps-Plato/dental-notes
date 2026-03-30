"""Tests for HealthChecker -- system component health monitoring.

Covers check_gpu, check_ollama, check_microphone, check_disk, check_network,
and check_all aggregation. Uses mocks/fakes for hardware dependencies.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dental_notes.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings with tmp_path storage for health tests."""
    return Settings(
        storage_dir=tmp_path / "transcripts",
        sessions_dir=tmp_path / "sessions",
    )


class TestComponentHealth:
    """ComponentHealth dataclass has name, healthy, and details."""

    def test_construction(self):
        from dental_notes.health import ComponentHealth

        h = ComponentHealth(name="gpu", healthy=True, details={"available": True})
        assert h.name == "gpu"
        assert h.healthy is True
        assert h.details == {"available": True}

    def test_unhealthy_component(self):
        from dental_notes.health import ComponentHealth

        h = ComponentHealth(name="gpu", healthy=False, details={"error": "no CUDA"})
        assert h.healthy is False


class TestCheckGpu:
    """HealthChecker.check_gpu() reports GPU availability."""

    def test_gpu_available(self, settings: Settings):
        """Returns healthy=True with device info when CUDA available."""
        from dental_notes.health import HealthChecker

        mock_props = MagicMock()
        mock_props.name = "NVIDIA GeForce GTX 1070 Ti"
        mock_props.total_mem = 8589934592  # 8GB in bytes

        with patch("dental_notes.health.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.get_device_properties.return_value = mock_props
            mock_torch.cuda.memory_allocated.return_value = 1073741824  # 1GB

            checker = HealthChecker(settings)
            result = checker.check_gpu()

        assert result.healthy is True
        assert result.details["available"] is True
        assert "1070" in result.details["name"]

    def test_gpu_unavailable(self, settings: Settings):
        """Returns healthy=False when CUDA not available."""
        from dental_notes.health import HealthChecker

        with patch("dental_notes.health.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False

            checker = HealthChecker(settings)
            result = checker.check_gpu()

        assert result.healthy is False
        assert result.details["available"] is False

    def test_gpu_torch_import_error(self, settings: Settings):
        """Returns healthy=False when torch is not importable."""
        from dental_notes.health import HealthChecker

        with patch("dental_notes.health.torch", None):
            checker = HealthChecker(settings)
            result = checker.check_gpu()

        assert result.healthy is False
        assert "error" in result.details


class TestCheckOllama:
    """HealthChecker.check_ollama() reports Ollama service status."""

    def test_ollama_available_and_model_ready(self, settings: Settings):
        from dental_notes.health import HealthChecker
        from tests.conftest import FakeOllamaService

        ollama = FakeOllamaService()
        checker = HealthChecker(settings, ollama_service=ollama)
        result = checker.check_ollama()

        assert result.healthy is True
        assert result.details["reachable"] is True
        assert result.details["model_ready"] is True

    def test_ollama_none(self, settings: Settings):
        """Returns healthy=False when ollama_service is None."""
        from dental_notes.health import HealthChecker

        checker = HealthChecker(settings, ollama_service=None)
        result = checker.check_ollama()

        assert result.healthy is False

    def test_ollama_unavailable(self, settings: Settings):
        """Returns healthy=False when ollama is not reachable."""
        from dental_notes.health import HealthChecker
        from tests.conftest import FakeOllamaService

        ollama = FakeOllamaService()
        ollama.is_available = lambda: False
        checker = HealthChecker(settings, ollama_service=ollama)
        result = checker.check_ollama()

        assert result.healthy is False
        assert result.details["reachable"] is False

    def test_ollama_model_not_ready(self, settings: Settings):
        """Returns healthy with model_ready=False when model not loaded."""
        from dental_notes.health import HealthChecker
        from tests.conftest import FakeOllamaService

        ollama = FakeOllamaService()
        ollama.is_model_ready = lambda: False
        checker = HealthChecker(settings, ollama_service=ollama)
        result = checker.check_ollama()

        # Reachable but model not ready -> degraded
        assert result.details["reachable"] is True
        assert result.details["model_ready"] is False


class TestCheckMicrophone:
    """HealthChecker.check_microphone() reports mic availability."""

    def test_microphone_available(self, settings: Settings):
        from dental_notes.health import HealthChecker

        with patch("dental_notes.health._list_input_devices") as mock_list:
            mock_list.return_value = [
                {"name": "Yeti Classic", "index": 0},
                {"name": "Built-in Mic", "index": 1},
            ]
            checker = HealthChecker(settings)
            result = checker.check_microphone()

        assert result.healthy is True
        assert result.details["device_count"] == 2
        assert result.details["available"] is True

    def test_no_microphone(self, settings: Settings):
        from dental_notes.health import HealthChecker

        with patch("dental_notes.health._list_input_devices") as mock_list:
            mock_list.return_value = []
            checker = HealthChecker(settings)
            result = checker.check_microphone()

        assert result.healthy is False
        assert result.details["available"] is False
        assert result.details["device_count"] == 0


class TestCheckDisk:
    """HealthChecker.check_disk() reports disk usage."""

    def test_disk_healthy(self, settings: Settings, tmp_path: Path):
        from dental_notes.health import HealthChecker

        # tmp_path should have plenty of space
        checker = HealthChecker(settings)
        result = checker.check_disk()

        assert result.healthy is True
        assert "free_gb" in result.details
        assert "total_gb" in result.details

    def test_disk_low_space_warning(self, settings: Settings):
        from dental_notes.health import HealthChecker

        with patch("dental_notes.health.shutil") as mock_shutil:
            # Simulate low disk: 500MB free of 100GB
            mock_shutil.disk_usage.return_value = MagicMock(
                free=500 * 1024 * 1024,  # 500MB
                total=100 * 1024 * 1024 * 1024,  # 100GB
            )
            checker = HealthChecker(settings)
            result = checker.check_disk()

        assert result.details["warning"] is True
        assert result.details["free_gb"] < 1.0


class TestCheckNetwork:
    """HealthChecker.check_network() is a forward-looking placeholder."""

    def test_network_placeholder_healthy(self, settings: Settings):
        from dental_notes.health import HealthChecker

        checker = HealthChecker(settings)
        result = checker.check_network()

        assert result.healthy is True


class TestCheckAll:
    """HealthChecker.check_all() aggregates all component checks."""

    def test_all_healthy_returns_ok(self, settings: Settings):
        from dental_notes.health import HealthChecker
        from tests.conftest import FakeOllamaService

        ollama = FakeOllamaService()
        checker = HealthChecker(settings, ollama_service=ollama)

        with (
            patch("dental_notes.health.torch") as mock_torch,
            patch("dental_notes.health._list_input_devices") as mock_mic,
        ):
            mock_props = MagicMock()
            mock_props.name = "GTX 1070 Ti"
            mock_props.total_mem = 8589934592
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.get_device_properties.return_value = mock_props
            mock_torch.cuda.memory_allocated.return_value = 0
            mock_mic.return_value = [{"name": "Yeti", "index": 0}]

            result = checker.check_all()

        assert result["status"] == "ok"
        assert "gpu" in result["checks"]
        assert "ollama" in result["checks"]
        assert "microphone" in result["checks"]
        assert "disk" in result["checks"]

    def test_degraded_when_gpu_unavailable(self, settings: Settings):
        from dental_notes.health import HealthChecker
        from tests.conftest import FakeOllamaService

        ollama = FakeOllamaService()
        checker = HealthChecker(settings, ollama_service=ollama)

        with (
            patch("dental_notes.health.torch") as mock_torch,
            patch("dental_notes.health._list_input_devices") as mock_mic,
        ):
            mock_torch.cuda.is_available.return_value = False
            mock_mic.return_value = [{"name": "Yeti", "index": 0}]

            result = checker.check_all()

        assert result["status"] == "degraded"

    def test_degraded_when_no_ollama(self, settings: Settings):
        from dental_notes.health import HealthChecker

        checker = HealthChecker(settings, ollama_service=None)

        with (
            patch("dental_notes.health.torch") as mock_torch,
            patch("dental_notes.health._list_input_devices") as mock_mic,
        ):
            mock_props = MagicMock()
            mock_props.name = "GTX 1070 Ti"
            mock_props.total_mem = 8589934592
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.get_device_properties.return_value = mock_props
            mock_torch.cuda.memory_allocated.return_value = 0
            mock_mic.return_value = [{"name": "Yeti", "index": 0}]

            result = checker.check_all()

        assert result["status"] == "degraded"
