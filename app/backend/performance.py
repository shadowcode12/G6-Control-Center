from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import glob
import shutil
import subprocess
from typing import Sequence

from app.backend.privileges import run_privileged


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class PerformanceController:
    """CPU and system performance controls exposed by Linux."""

    PROFILE_ALIASES = {
        "silent": "power-saver",
        "balanced": "balanced",
        "performance": "performance",
        "gaming": "performance",
    }

    # Friendly UI labels are kept separate from the kernel EPP strings.
    EPP_OPTIONS = (
        "power",
        "balance_power",
        "performance",
    )

    EPP_LABELS = {
        "power": "Low",
        "balance_power": "Mid",
        "performance": "High",
    }

    def __init__(self) -> None:
        self._profile_command = shutil.which("powerprofilesctl")

    def _run(self, args: Sequence[str], timeout: float = 4.0) -> CommandResult:
        try:
            result = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return CommandResult(
                ok=result.returncode == 0,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                returncode=result.returncode,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return CommandResult(ok=False, stderr=str(exc), returncode=-1)

    @property
    def available(self) -> bool:
        return self._profile_command is not None

    def available_profiles(self) -> list[str]:
        if not self.available:
            return []

        result = self._run([self._profile_command, "list"])
        if not result.ok:
            return []

        return [
            profile
            for profile in ("power-saver", "balanced", "performance")
            if profile in result.stdout
        ]

    def current_profile(self) -> str | None:
        if not self.available:
            return None
        result = self._run([self._profile_command, "get"])
        return result.stdout.lower() if result.ok and result.stdout else None

    def set_profile(self, profile: str) -> CommandResult:
        if not self.available:
            return CommandResult(
                ok=False,
                stderr="powerprofilesctl is not installed.",
                returncode=127,
            )

        normalized = self.PROFILE_ALIASES.get(profile.lower(), profile.lower())
        if normalized not in {"power-saver", "balanced", "performance"}:
            return CommandResult(
                ok=False,
                stderr=f"Unsupported profile: {profile}",
                returncode=2,
            )

        return self._run(
            [self._profile_command, "set", normalized],
            timeout=5,
        )

    @staticmethod
    def _read(path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    def cpu_driver(self) -> str | None:
        return self._read(
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"
        )

    def energy_performance_preference(self) -> str | None:
        path = (
            "/sys/devices/system/cpu/cpu0/cpufreq/"
            "energy_performance_preference"
        )
        return self._read(path)

    def set_epp(self, value: str) -> CommandResult:
        if value not in self.EPP_OPTIONS:
            return CommandResult(
                ok=False,
                stderr=f"Unsupported EPP: {value}",
                returncode=2,
            )

        result = run_privileged(["epp", value])
        return CommandResult(
            ok=result.ok,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def turbo_enabled(self) -> bool | None:
        no_turbo = self._read(
            "/sys/devices/system/cpu/intel_pstate/no_turbo"
        )
        if no_turbo is not None:
            return no_turbo == "0"

        boost = self._read(
            "/sys/devices/system/cpu/cpufreq/boost"
        )
        if boost is not None:
            return boost == "1"

        return None

    def set_turbo_enabled(self, enabled: bool) -> CommandResult:
        result = run_privileged(
            ["turbo", "on" if enabled else "off"]
        )
        return CommandResult(
            ok=result.ok,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def state(self) -> dict:
        return {
            "profile": self.current_profile(),
            "driver": self.cpu_driver(),
            "epp": self.energy_performance_preference(),
            "turbo": self.turbo_enabled(),
        }
