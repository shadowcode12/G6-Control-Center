from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.backend.privileges import run_privileged


STATE_FILE = Path("/var/lib/g6-control-center/keyboard.json")


class KeyboardController:
    """
    Native G6 KF single-zone RGB keyboard backend.

    The G6 KF uses the Clevo EC keyboard mailbox. This controller never calls
    gigactl or any third-party keyboard CLI.
    """

    PRESETS = {
        "Blue": (0, 0, 255),
        "Red": (255, 0, 0),
        "Green": (0, 255, 0),
        "Yellow": (255, 180, 0),
        "Orange": (255, 80, 0),
        "Cyan": (0, 255, 255),
        "Purple": (160, 0, 255),
        "Pink": (255, 0, 120),
        "White": (255, 255, 255),
    }

    def _read_state(self) -> dict[str, Any]:
        try:
            state = json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )
        except (
            FileNotFoundError,
            PermissionError,
            OSError,
            json.JSONDecodeError,
        ):
            state = {
                "enabled": True,
                "r": 0,
                "g": 0,
                "b": 255,
                "brightness": 100,
            }

        return {
            "enabled": bool(state.get("enabled", True)),
            "r": max(0, min(255, int(state.get("r", 0)))),
            "g": max(0, min(255, int(state.get("g", 0)))),
            "b": max(0, min(255, int(state.get("b", 255)))),
            "brightness": max(
                0,
                min(100, int(state.get("brightness", 100))),
            ),
        }

    @property
    def available(self) -> bool:
        """The write backend is available only on a verified G6 KF."""
        return self._is_g6_kf()

    @staticmethod
    def _is_g6_kf() -> bool:
        try:
            vendor = Path(
                "/sys/class/dmi/id/sys_vendor"
            ).read_text(
                encoding="utf-8",
                errors="ignore",
            ).strip()

            model = Path(
                "/sys/class/dmi/id/product_name"
            ).read_text(
                encoding="utf-8",
                errors="ignore",
            ).strip()

            return (
                vendor.lower().startswith("gigabyte")
                and model == "G6 KF"
            )
        except OSError:
            return False

    def state(self) -> dict[str, Any]:
        state = self._read_state()
        state["available"] = self.available
        state["single_zone"] = True
        state["model"] = "Gigabyte G6 KF"
        return state

    @staticmethod
    def _result(result) -> tuple[bool, str]:
        return (
            result.ok,
            result.stderr or result.stdout,
        )

    def set_color(
        self,
        r: int,
        g: int,
        b: int,
    ) -> tuple[bool, str]:
        if not self.available:
            return (
                False,
                "Native RGB control is hardware-validated only on Gigabyte G6 KF.",
            )

        result = run_privileged(
            [
                "keyboard-color",
                str(max(0, min(255, int(r)))),
                str(max(0, min(255, int(g)))),
                str(max(0, min(255, int(b)))),
            ],
            timeout=10,
        )
        return self._result(result)

    def set_brightness(
        self,
        percent: int,
    ) -> tuple[bool, str]:
        if not self.available:
            return (
                False,
                "Native RGB control is hardware-validated only on Gigabyte G6 KF.",
            )

        result = run_privileged(
            [
                "keyboard-brightness",
                str(max(0, min(100, int(percent)))),
            ],
            timeout=10,
        )
        return self._result(result)

    def set_enabled(
        self,
        enabled: bool,
    ) -> tuple[bool, str]:
        if not self.available:
            return (
                False,
                "Native RGB control is hardware-validated only on Gigabyte G6 KF.",
            )

        result = run_privileged(
            [
                "keyboard-enabled",
                "true" if enabled else "false",
            ],
            timeout=10,
        )
        return self._result(result)
