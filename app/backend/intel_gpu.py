from __future__ import annotations

from pathlib import Path
import glob
from typing import Any


INTEL_VENDOR = "0x8086"


class IntelGpuController:
    """Read-only Intel iGPU telemetry from standard Linux sysfs interfaces."""

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    @classmethod
    def _number(cls, paths: list[Path], scale: float = 1.0) -> float | None:
        for path in paths:
            raw = cls._read(path)
            if raw is None:
                continue
            try:
                return float(raw) / scale
            except ValueError:
                continue
        return None

    @classmethod
    def _device_paths(cls) -> list[Path]:
        devices: list[Path] = []
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
            vendor = cls._read(card / "device/vendor")
            if vendor and vendor.lower() == INTEL_VENDOR:
                devices.append(card / "device")
        return devices

    @classmethod
    def _temperature(cls, device: Path) -> float | None:
        candidates = [
            path
            for hwmon in sorted((device / "hwmon").glob("hwmon*"))
            for path in sorted(hwmon.glob("temp*_input"))
        ]
        value = cls._number(candidates, scale=1000.0)
        return value

    @classmethod
    def _power(cls, device: Path) -> float | None:
        candidates = []
        for hwmon in sorted((device / "hwmon").glob("hwmon*")):
            candidates.extend(sorted(hwmon.glob("power*_average")))
            candidates.extend(sorted(hwmon.glob("power*_input")))
        return cls._number(candidates, scale=1_000_000.0)

    @classmethod
    def _utilization(cls, device: Path) -> float | None:
        candidates = [
            device / "gpu_busy_percent",
            device / "gt" / "gt0" / "gt_busy_percent",
        ]
        return cls._number(candidates)

    @classmethod
    def _frequency(cls, device: Path) -> float | None:
        candidates = [
            device / "gt_cur_freq_mhz",
            device / "gt_act_freq_mhz",
            device / "gt" / "gt0" / "rps_cur_freq_mhz",
            device / "gt" / "gt0" / "rps_act_freq_mhz",
        ]
        return cls._number(candidates)

    @classmethod
    def _memory(cls, device: Path) -> tuple[float | None, float | None]:
        used = cls._number(
            [
                device / "mem_info_vram_used",
                device / "mem_info_ggtt_used",
            ],
            scale=1024 * 1024,
        )
        total = cls._number(
            [
                device / "mem_info_vram_total",
                device / "mem_info_ggtt_total",
            ],
            scale=1024 * 1024,
        )
        return used, total

    @classmethod
    def _name(cls, device: Path) -> str:
        uevent = cls._read(device / "uevent") or ""
        driver = "i915"
        for line in uevent.splitlines():
            if line.startswith("DRIVER="):
                driver = line.partition("=")[2] or driver
                break
        return f"Intel Graphics ({driver})"

    def get_gpu_info(self) -> dict[str, Any]:
        devices = self._device_paths()
        if not devices:
            return {
                "available": False,
                "vendor": "intel",
                "reason": "No Intel DRM GPU was detected.",
            }

        device = devices[0]
        memory_used, memory_total = self._memory(device)

        return {
            "available": True,
            "vendor": "intel",
            "name": self._name(device),
            "temperature": self._temperature(device),
            "usage": self._utilization(device),
            "power": self._power(device),
            "power_limit": None,
            "memory_used": memory_used,
            "memory_total": memory_total,
            "graphics_clock": self._frequency(device),
            "memory_clock": None,
        }
