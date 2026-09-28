from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
from typing import Sequence


@dataclass(frozen=True)
class PrivilegedResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def _helper_path() -> Path | None:
    explicit = os.environ.get("G6CC_HELPER")
    if explicit:
        candidate = Path(explicit)
        if candidate.exists():
            return candidate

    repo_helper = Path(__file__).resolve().parents[1] / "services" / "privileged_helper.py"
    if repo_helper.exists():
        return repo_helper

    installed = Path("/usr/lib/g6-control-center/privileged_helper.py")
    if installed.exists():
        return installed

    return None


def run_privileged(args: Sequence[str], timeout: float = 15) -> PrivilegedResult:
    pkexec = shutil.which("pkexec")
    python = shutil.which("python3") or "/usr/bin/python3"
    helper = _helper_path()

    if not pkexec or helper is None:
        return PrivilegedResult(
            ok=False,
            stderr="pkexec or the privileged helper is not installed.",
            returncode=127,
        )

    try:
        result = subprocess.run(
            [pkexec, python, str(helper), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return PrivilegedResult(
            ok=result.returncode == 0,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            returncode=result.returncode,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return PrivilegedResult(ok=False, stderr=str(exc), returncode=-1)
