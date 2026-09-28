from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import stat
import subprocess
from typing import Sequence


@dataclass(frozen=True)
class PrivilegedResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def _safe_helper(path: Path | None) -> Path | None:
    if path is None or not path.exists():
        return None

    try:
        info = path.stat()
    except OSError:
        return None

    # The helper must be root-owned and not writable by group/other users.
    if info.st_uid != 0:
        return None

    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None

    return path


def _helper_path() -> Path | None:
    installed = _safe_helper(
        Path("/usr/lib/g6-control-center/privileged_helper.py")
    )
    if installed:
        return installed

    # Explicit developer override is accepted only when the caller points to
    # a root-owned, non-world-writable helper.
    explicit = os.environ.get("G6CC_HELPER")
    if explicit:
        return _safe_helper(Path(explicit))

    return None


def run_privileged(
    args: Sequence[str],
    timeout: float = 15,
) -> PrivilegedResult:
    pkexec = shutil.which("pkexec")
    python = shutil.which("python3") or "/usr/bin/python3"
    helper = _helper_path()

    if not pkexec:
        return PrivilegedResult(
            ok=False,
            stderr="PolicyKit (pkexec) is not installed.",
            returncode=127,
        )

    if helper is None:
        return PrivilegedResult(
            ok=False,
            stderr=(
                "The root-owned helper is not installed. "
                "Run packaging/install.sh first."
            ),
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
