"""System health monitoring for dental-notes components.

HealthChecker reports the status of GPU, Ollama, microphone, disk, and
network as structured data. Each check returns a ComponentHealth with
name, healthy flag, and details dict.

All checks are synchronous -- async routes should run them in an executor.
Hardware dependencies (torch, sounddevice) are imported lazily and wrapped
in try/except so missing packages don't crash the health module.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from typing import Any

from dental_notes.config import Settings

logger = logging.getLogger(__name__)

# Lazy import torch -- may not be available in CI/test environments
try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]


def _list_input_devices() -> list[dict[str, Any]]:
    """List available audio input devices.

    Tries sounddevice.query_devices() and filters for input-capable devices.
    Returns empty list if sounddevice is not importable.
    """
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        return [
            {"name": d["name"], "index": i}
            for i, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]
    except Exception:
        logger.warning("Could not query audio devices", exc_info=True)
        return []


@dataclass
class ComponentHealth:
    """Health status of a single system component."""

    name: str
    healthy: bool
    details: dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Reports health status of all dental-notes system components.

    Designed to be called from a synchronous context. Async routes
    should use run_in_executor() to avoid blocking the event loop.
    """

    def __init__(self, settings: Settings, ollama_service: Any = None) -> None:
        self._settings = settings
        self._ollama = ollama_service

    def check_gpu(self) -> ComponentHealth:
        """Check CUDA GPU availability and memory status."""
        if torch is None:
            return ComponentHealth(
                name="gpu",
                healthy=False,
                details={"available": False, "error": "torch not installed"},
            )
        try:
            available = torch.cuda.is_available()
            if not available:
                return ComponentHealth(
                    name="gpu",
                    healthy=False,
                    details={"available": False},
                )
            props = torch.cuda.get_device_properties(0)
            allocated = torch.cuda.memory_allocated(0)
            return ComponentHealth(
                name="gpu",
                healthy=True,
                details={
                    "available": True,
                    "name": props.name,
                    "total_memory_mb": round(props.total_mem / (1024 * 1024)),
                    "allocated_mb": round(allocated / (1024 * 1024)),
                },
            )
        except Exception as e:
            return ComponentHealth(
                name="gpu",
                healthy=False,
                details={"available": False, "error": str(e)},
            )

    def check_ollama(self) -> ComponentHealth:
        """Check Ollama service reachability and model readiness."""
        if self._ollama is None:
            return ComponentHealth(
                name="ollama",
                healthy=False,
                details={"reachable": False, "error": "no ollama_service configured"},
            )
        try:
            reachable = self._ollama.is_available()
            model_ready = self._ollama.is_model_ready() if reachable else False
            return ComponentHealth(
                name="ollama",
                healthy=reachable and model_ready,
                details={
                    "reachable": reachable,
                    "model_ready": model_ready,
                },
            )
        except Exception as e:
            return ComponentHealth(
                name="ollama",
                healthy=False,
                details={"reachable": False, "error": str(e)},
            )

    def check_microphone(self) -> ComponentHealth:
        """Check available audio input devices."""
        try:
            devices = _list_input_devices()
            available = len(devices) > 0
            return ComponentHealth(
                name="microphone",
                healthy=available,
                details={
                    "available": available,
                    "device_count": len(devices),
                    "devices": [d["name"] for d in devices[:5]],
                },
            )
        except Exception as e:
            return ComponentHealth(
                name="microphone",
                healthy=False,
                details={"available": False, "device_count": 0, "error": str(e)},
            )

    def check_disk(self) -> ComponentHealth:
        """Check disk space for storage directory.

        Falls back to parent directory if storage_dir doesn't exist yet.
        """
        try:
            check_path = self._settings.storage_dir
            if not check_path.exists():
                check_path = check_path.parent
            usage = shutil.disk_usage(check_path)
            free_gb = round(usage.free / (1024 ** 3), 2)
            total_gb = round(usage.total / (1024 ** 3), 2)
            warning = free_gb < 1.0
            return ComponentHealth(
                name="disk",
                healthy=not warning,
                details={
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "warning": warning,
                },
            )
        except Exception as e:
            return ComponentHealth(
                name="disk",
                healthy=False,
                details={"error": str(e)},
            )

    def check_network(self) -> ComponentHealth:
        """Placeholder for split architecture network check (Phase 6)."""
        return ComponentHealth(
            name="network",
            healthy=True,
            details={"note": "split architecture not configured"},
        )

    def check_all(self) -> dict[str, Any]:
        """Run all health checks and return aggregated status.

        Returns dict with:
        - status: "ok" if all healthy, "degraded" if any unhealthy
        - checks: dict of component name -> ComponentHealth details
        """
        checks = {
            "gpu": self.check_gpu(),
            "ollama": self.check_ollama(),
            "microphone": self.check_microphone(),
            "disk": self.check_disk(),
            "network": self.check_network(),
        }
        all_healthy = all(c.healthy for c in checks.values())
        return {
            "status": "ok" if all_healthy else "degraded",
            "checks": {
                name: {"healthy": c.healthy, **c.details}
                for name, c in checks.items()
            },
        }
