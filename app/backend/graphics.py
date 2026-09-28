from __future__ import annotations

from typing import Any

from app.backend.intel_gpu import IntelGpuController
from app.backend.nvidia import NvidiaController


class GraphicsController:
    """
    Unified read-only GPU backend.

    PRIME mode selects the preferred GPU when possible:
      - nvidia: NVIDIA
      - intel: Intel
      - on-demand: Intel for the always-on desktop path
    Both devices remain detectable, so the UI can explain what is present.
    """

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
        elif mode == "intel" and intel.get("available"):
            preferred = intel
        elif mode == "on-demand" and intel.get("available"):
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

    def get_power_limits(self) -> dict[str, Any]:
        gpu = self.preferred_gpu()
        if gpu.get("vendor") != "nvidia":
            return {
                "available": False,
                "reason": "GPU power-limit control is only exposed for NVIDIA.",
            }
        return self.nvidia.get_power_limits()

    def set_power_limit(self, watts: float) -> tuple[bool, str]:
        gpu = self.preferred_gpu()
        if gpu.get("vendor") != "nvidia":
            return False, "GPU power-limit control is only available for NVIDIA."
        return self.nvidia.set_power_limit(watts)

    def set_prime_mode(self, mode: str) -> tuple[bool, str]:
        return self.nvidia.set_prime_mode(mode)
