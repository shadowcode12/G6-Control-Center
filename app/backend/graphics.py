from __future__ import annotations

from typing import Any

from app.backend.intel_gpu import IntelGpuController
from app.backend.nvidia import NvidiaController


class GraphicsController:
    """Unified read-only Intel/NVIDIA GPU telemetry with PRIME detection."""

    def __init__(self) -> None:
        self.nvidia = NvidiaController()
        self.intel = IntelGpuController()

    def prime_mode(self) -> str | None:
        return self.nvidia.prime_mode()

    def snapshot(self) -> dict[str, Any]:
        nvidia = self.nvidia.get_gpu_info()
        intel = self.intel.get_gpu_info()
        mode = self.prime_mode()

        preferred: dict[str, Any] | None = None

        if mode == "nvidia" and nvidia.get("available"):
            preferred = nvidia
        elif mode in {"intel", "on-demand"} and intel.get("available"):
            preferred = intel
        elif nvidia.get("available"):
            preferred = nvidia
        elif intel.get("available"):
            preferred = intel

        return {
            "available": preferred is not None,
            "selected": preferred,
            "prime": mode,
            "nvidia": nvidia,
            "intel": intel,
        }

    def preferred_gpu(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return snapshot.get("selected") or {
            "available": False,
            "vendor": "unknown",
            "reason": "No supported GPU telemetry source was detected.",
        }

    def get_default_power(self) -> dict[str, Any]:
        """Read-only NVIDIA default power/TGP information."""
        info = self.nvidia.get_power_limits()
        if not info.get("available"):
            return info

        return {
            "available": True,
            "name": info.get("name"),
            "default": info.get("default"),
        }

    def set_prime_mode(self, mode: str) -> tuple[bool, str]:
        return self.nvidia.set_prime_mode(mode)
