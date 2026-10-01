from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.backend.privileges import run_privileged


STATE_FILE = Path("/var/lib/g6-control-center/keyboard.json")


class KeyboardController:
    """Native single-zone RGB keyboard backend for the verified G6 KF."""

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
            raw = json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )
        except (
            FileNotFoundError,
            PermissionError,
            OSError,
            json.JSONDecodeError,
        ):
            raw = {}

        try:
            return {
                "enabled": bool(raw.get("enabled", True)),
                "r": max(0, min(255, int(raw.get("r", 0)))),
                "g": max(0, min(255, int(raw.get("g", 0)))),
                "b": max(0, min(255, int(raw.get("b", 255)))),
                "brightness": max(
                    0,
                    min(100, int(raw.get("brightness", 100))),
                ),
            }
        except (TypeError, ValueError):
            return {
                "enabled": True,
                "r": 0,
                "g": 0,
                "b": 255,
                "brightness": 100,
            }

    @staticmethod
    def _dmi_value(name: str) -> str:
        try:
            return Path(
                f"/sys/class/dmi/id/{name}"
            ).read_text(
                encoding="utf-8",
                errors="ignore",
            ).strip()
        except OSError:
            return ""

    @classmethod
    def _is_g6_kf(cls) -> bool:
        return (
            cls._dmi_value("sys_vendor").lower().startswith("gigabyte")
            and cls._dmi_value("product_name") == "G6 KF"
        )

    @classmethod
    def _ec_ready(cls) -> bool:
        if not Path("/sys/kernel/debug/ec/ec0/io").exists():
            return False

        try:
            support = Path(
                "/sys/module/ec_sys/parameters/write_support"
            ).read_text(encoding="utf-8").strip().upper()
        except OSError:
            return False

        return support in {"Y", "1"}

    @property
    def available(self) -> bool:
        return self._is_g6_kf() and self._ec_ready()

    def state(self) -> dict[str, Any]:
        state = self._read_state()
        state.update(
            {
                "available": self.available,
                "single_zone": True,
                "model": "Gigabyte G6 KF",
            }
        )
        return state

    @staticmethod
    def _message(result) -> str:
        return result.stderr or result.stdout or ""

    def set_color(self, r: int, g: int, b: int) -> tuple[bool, str]:
        if not self._is_g6_kf():
            return False, "Native RGB control is currently validated only on G6 KF."

        result = run_privileged(
            [
                "keyboard-color",
                str(max(0, min(255, int(r)))),
                str(max(0, min(255, int(g)))),
                str(max(0, min(255, int(b)))),
            ],
            timeout=10,
        )
        return result.ok, self._message(result)

    def set_brightness(self, percent: int) -> tuple[bool, str]:
        if not self._is_g6_kf():
            return False, "Native RGB control is currently validated only on G6 KF."

        result = run_privileged(
            [
                "keyboard-brightness",
                str(max(0, min(100, int(percent)))),
            ],
            timeout=10,
        )
        return result.ok, self._message(result)

    def set_enabled(self, enabled: bool) -> tuple[bool, str]:
        if not self._is_g6_kf():
            return False, "Native RGB control is currently validated only on G6 KF."

        result = run_privileged(
            [
                "keyboard-enabled",
                "true" if enabled else "false",
            ],
            timeout=10,
        )
        return result.ok, self._message(result)
