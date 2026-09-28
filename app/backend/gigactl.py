from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class GigaCtlController:
    """Safe wrapper around gigactl's GigaControl CLI."""

    def __init__(self) -> None:
        self.gfan = shutil.which("gfan")
        self.gkbd = shutil.which("gkbd")

    @property
    def available(self) -> bool:
        return bool(self.gfan and self.gkbd)

    def _run(self, command: str | None, args: Sequence[str]) -> CommandResult:
        if not command:
            return CommandResult(False, stderr="gigactl is not installed.", returncode=127)
        try:
            result = subprocess.run(
                [command, *args],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return CommandResult(
                ok=result.returncode == 0,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                returncode=result.returncode,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return CommandResult(False, stderr=str(exc), returncode=-1)

    def fan_status(self) -> CommandResult:
        return self._run(self.gfan, [])

    def set_fans_auto(self) -> CommandResult:
        return self._run(self.gfan, ["auto"])

    def set_fans(self, cpu_percent: int, gpu_percent: int | None = None) -> CommandResult:
        cpu_percent = max(30, min(100, int(cpu_percent)))
        if gpu_percent is None:
            return self._run(self.gfan, [str(cpu_percent)])
        gpu_percent = max(30, min(100, int(gpu_percent)))
        return self._run(self.gfan, [str(cpu_percent), str(gpu_percent)])

    def keyboard_status(self) -> CommandResult:
        return self._run(self.gkbd, ["status"])

    def keyboard_color(self, color: str) -> CommandResult:
        color = color.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            return CommandResult(False, stderr="Color must be a 6-digit hexadecimal value.", returncode=2)
        return self._run(self.gkbd, [color])

    def keyboard_brightness(self, percent: int) -> CommandResult:
        percent = max(0, min(100, int(percent)))
        return self._run(self.gkbd, ["brightness", str(percent)])

    def keyboard_on(self) -> CommandResult:
        return self._run(self.gkbd, ["on"])

    def keyboard_off(self) -> CommandResult:
        return self._run(self.gkbd, ["off"])
