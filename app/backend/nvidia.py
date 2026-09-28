from __future__ import annotations

import shutil
import subprocess

from app.backend.privileges import run_privileged


class NvidiaController:
    def __init__(self) -> None:
        self.command = shutil.which("nvidia-smi")
        self.prime_select = shutil.which("prime-select")

    def _run(self, args: list[str], timeout: float = 3):
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

    def get_gpu_info(self) -> dict:
        if not self.command:
            return {"available": False, "reason": "nvidia-smi not found"}

        result = self._run([
            "--query-gpu=name,temperature.gpu,utilization.gpu,"
            "power.draw,power.limit,memory.used,memory.total,clocks.gr,clocks.mem",
            "--format=csv,noheader,nounits",
        ])
        if result is None or result.returncode != 0:
            return {"available": False, "reason": "NVIDIA GPU unavailable"}

        values = [item.strip() for item in result.stdout.strip().split(",")]
        if len(values) < 8:
            return {"available": False, "reason": "Unexpected nvidia-smi output"}

        try:
            return {
                "available": True,
                "name": values[0],
                "temperature": float(values[1]),
                "usage": float(values[2]),
                "power": float(values[3]),
                "power_limit": float(values[4]),
                "memory_used": float(values[5]),
                "memory_total": float(values[6]),
                "graphics_clock": float(values[7]),
                "memory_clock": float(values[8]) if len(values) > 8 else None,
            }
        except ValueError:
            return {"available": False, "reason": "Invalid nvidia-smi data"}

    def get_power_limits(self) -> dict:
        if not self.command:
            return {"available": False}

        result = self._run([
            "--query-gpu=name,power.default_limit,power.min_limit,power.max_limit",
            "--format=csv,noheader,nounits",
        ])
        if result is None or result.returncode != 0:
            return {"available": False}

        values = [item.strip() for item in result.stdout.strip().split(",")]
        if len(values) < 4:
            return {"available": False}

        try:
            return {
                "available": True,
                "name": values[0],
                "default": float(values[1]),
                "minimum": float(values[2]),
                "maximum": float(values[3]),
            }
        except ValueError:
            return {"available": False}

    def set_power_limit(self, watts: float) -> tuple[bool, str]:
        limits = self.get_power_limits()
        if not limits.get("available"):
            return False, "NVIDIA power-limit range is unavailable."

        minimum = float(limits["minimum"])
        maximum = float(limits["maximum"])
        if not minimum <= watts <= maximum:
            return False, f"Choose a limit between {minimum:.0f} W and {maximum:.0f} W."

        direct = self._run(["--power-limit", f"{watts:.1f}"], timeout=5)
        if direct is not None and direct.returncode == 0:
            return True, direct.stdout.strip()

        privileged = run_privileged(["gpu-power-limit", f"{watts:.1f}"], timeout=10)
        return privileged.ok, privileged.stderr or privileged.stdout

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
        return result.stdout.strip().lower() or None

    def set_prime_mode(self, mode: str) -> tuple[bool, str]:
        if mode not in {"intel", "on-demand", "nvidia"}:
            return False, "Unsupported PRIME mode."
        result = run_privileged(["prime-mode", mode], timeout=15)
        return result.ok, result.stderr or result.stdout
