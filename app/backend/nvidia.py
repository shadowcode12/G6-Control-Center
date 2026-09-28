from __future__ import annotations

import shutil
import subprocess
from typing import Any

from app.backend.privileges import run_privileged


class NvidiaController:
    """NVIDIA telemetry and control adapter."""

    def __init__(self) -> None:
        self.command = shutil.which("nvidia-smi")
        self.prime_select = shutil.which("prime-select")

    def _run(
        self,
        args: list[str],
        timeout: float = 3.0,
    ) -> subprocess.CompletedProcess[str] | None:
        if not self.command:
            return None
        try:
            return subprocess.run(
                [self.command, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _float(value: str) -> float | None:
        value = value.strip()
        if not value or value.upper() in {
            "N/A",
            "NA",
            "UNKNOWN",
            "NOT_SUPPORTED",
            "[NOT_SUPPORTED]",
            "[NOT SUPPORTED]",
        }:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @classmethod
    def _parse_gpu_row(cls, row: str) -> dict[str, Any]:
        values = [item.strip() for item in row.split(",")]
        if len(values) < 9:
            return {
                "available": False,
                "vendor": "nvidia",
                "reason": "Unexpected nvidia-smi output.",
            }

        return {
            "available": True,
            "vendor": "nvidia",
            "name": values[0],
            "temperature": cls._float(values[1]),
            "usage": cls._float(values[2]),
            "power": cls._float(values[3]),
            "power_limit": cls._float(values[4]),
            "memory_used": cls._float(values[5]),
            "memory_total": cls._float(values[6]),
            "graphics_clock": cls._float(values[7]),
            "memory_clock": cls._float(values[8]),
        }

    def get_gpus(self) -> list[dict[str, Any]]:
        if not self.command:
            return []

        result = self._run(
            [
                "--query-gpu=name,temperature.gpu,utilization.gpu,"
                "power.draw,power.limit,memory.used,memory.total,"
                "clocks.gr,clocks.mem",
                "--format=csv,noheader,nounits",
            ]
        )

        if result is None or result.returncode != 0:
            return []

        return [
            self._parse_gpu_row(line.strip())
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    def get_gpu_info(self) -> dict[str, Any]:
        gpus = self.get_gpus()
        if not gpus:
            if not self.command:
                return {
                    "available": False,
                    "vendor": "nvidia",
                    "reason": "nvidia-smi not found.",
                }
            return {
                "available": False,
                "vendor": "nvidia",
                "reason": "NVIDIA GPU telemetry is unavailable.",
            }

        return gpus[0]

    def get_power_limits(self) -> dict[str, Any]:
        if not self.command:
            return {
                "available": False,
                "reason": "nvidia-smi not found.",
            }

        result = self._run(
            [
                "--query-gpu=name,power.default_limit,"
                "power.min_limit,power.max_limit",
                "--format=csv,noheader,nounits",
            ]
        )

        if result is None or result.returncode != 0:
            return {
                "available": False,
                "reason": "NVIDIA power-limit information is unavailable.",
            }

        values = [item.strip() for item in result.stdout.strip().split(",")]
        if len(values) < 4:
            return {
                "available": False,
                "reason": "Unexpected NVIDIA power-limit output.",
            }

        default = self._float(values[1])
        minimum = self._float(values[2])
        maximum = self._float(values[3])

        if default is None or minimum is None or maximum is None:
            return {
                "available": False,
                "reason": "NVIDIA did not expose a writable power-limit range.",
                "default": default,
                "minimum": minimum,
                "maximum": maximum,
            }

        return {
            "available": True,
            "name": values[0],
            "default": default,
            "minimum": minimum,
            "maximum": maximum,
        }


    def prime_mode(self) -> str | None:
        if not self.prime_select:
            return None

        try:
            result = subprocess.run(
                [self.prime_select, "query"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

        if result.returncode != 0:
            return None

        mode = result.stdout.strip().lower()
        if mode.startswith("nvidia"):
            return "nvidia"
        if mode.startswith("on-demand"):
            return "on-demand"
        if mode.startswith("intel"):
            return "intel"
        return mode or None

    def set_prime_mode(self, mode: str) -> tuple[bool, str]:
        if mode not in {"intel", "on-demand", "nvidia"}:
            return False, "Unsupported PRIME mode."

        result = run_privileged(
            ["prime-mode", mode],
            timeout=15,
        )
        return result.ok, result.stderr or result.stdout


# Backwards-compatible module API for small scripts/tests.


_controller = NvidiaController()


def get_gpu_info() -> dict[str, Any]:
    return _controller.get_gpu_info()


def get_power_limits() -> dict[str, Any]:
    return _controller.get_power_limits()




def prime_mode() -> str | None:
    return _controller.prime_mode()


def set_prime_mode(mode: str) -> tuple[bool, str]:
    return _controller.set_prime_mode(mode)
