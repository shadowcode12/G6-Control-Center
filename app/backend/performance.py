from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class PerformanceController:
    """Linux CPU/system performance controls.

    The controller intentionally uses documented Linux interfaces instead of
    touching the laptop EC. Gigabyte-specific EC controls remain delegated
    to gigactl.
    """

    PROFILE_ALIASES = {
        "silent": "power-saver",
        "balanced": "balanced",
        "performance": "performance",
        "gaming": "performance",
    }

    def __init__(self) -> None:
        self._profile_command = self._find_command("powerprofilesctl")

    @staticmethod
    def _find_command(command: str) -> str | None:
        try:
            result = subprocess.run(
                ["bash", "-lc", f"command -v {command}"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except subprocess.SubprocessError:
            return None

        path = result.stdout.strip()
        return path or None

    def _run(self, args: Sequence[str], timeout: float = 3) -> CommandResult:
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

        supported = []
        for profile in ("power-saver", "balanced", "performance"):
            if profile in result.stdout:
                supported.append(profile)

        return supported

    def current_profile(self) -> str | None:
        if not self.available:
            return None

        result = self._run([self._profile_command, "get"])
        if not result.ok:
            return None

        value = result.stdout.strip().lower()
        return value or None

    def set_profile(self, profile: str) -> CommandResult:
        if not self.available:
            return CommandResult(
                ok=False,
                stderr="powerprofilesctl is not installed.",
                returncode=-1,
            )

        normalized = self.PROFILE_ALIASES.get(profile.lower(), profile.lower())
        allowed = {"power-saver", "balanced", "performance"}

        if normalized not in allowed:
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
    def _read_text(path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    @staticmethod
    def _write_text(path: str, value: str) -> CommandResult:
        try:
            Path(path).write_text(value, encoding="utf-8")
            return CommandResult(ok=True)
        except PermissionError:
            return CommandResult(
                ok=False,
                stderr="Permission denied. A privileged helper is required.",
                returncode=13,
            )
        except OSError as exc:
            return CommandResult(ok=False, stderr=str(exc), returncode=1)

    def cpu_driver(self) -> str | None:
        return self._read_text(
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"
        )

    def energy_performance_preference(self) -> str | None:
        path = (
            "/sys/devices/system/cpu/cpu0/cpufreq/"
            "energy_performance_preference"
        )
        return self._read_text(path)

    def turbo_enabled(self) -> bool | None:
        no_turbo = self._read_text(
            "/sys/devices/system/cpu/intel_pstate/no_turbo"
        )
        if no_turbo is None:
            return None
        return no_turbo == "0"

    def set_turbo_enabled(self, enabled: bool) -> CommandResult:
        path = "/sys/devices/system/cpu/intel_pstate/no_turbo"
        return self._write_text(path, "0" if enabled else "1")
