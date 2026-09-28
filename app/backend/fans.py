from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


TELEMETRY_PATH = Path("/run/g6-control-center/telemetry.json")
MAX_SNAPSHOT_AGE = 3.0


class FanController:
    """
    Native fan telemetry backend.

    It does not call gigactl. The root-owned telemetry service reads the
    G6 KF EC and publishes a short-lived read-only snapshot. Standard hwmon
    fan inputs are used only as a fallback when the native snapshot is absent.
    """

    def __init__(
        self,
        telemetry_path: str | Path = TELEMETRY_PATH,
    ) -> None:
        self.telemetry_path = Path(telemetry_path)

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    def _read_native_snapshot(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(
                self.telemetry_path.read_text(encoding="utf-8")
            )
        except (
            FileNotFoundError,
            PermissionError,
            OSError,
            json.JSONDecodeError,
        ):
            return None

        timestamp = payload.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            timestamp = 0.0

        if time.time() - timestamp > MAX_SNAPSHOT_AGE:
            return {
                "available": False,
                "source": payload.get("source", "native-ec"),
                "reason": "Native EC telemetry is stale.",
                "fans": [],
                "timestamp": timestamp,
            }

        return payload

    def _read_hwmon(self) -> dict[str, Any] | None:
        """Use generic hwmon fan RPM only when the native EC snapshot is absent."""
        fans: list[dict[str, Any]] = []

        for hwmon in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
            name = self._read_text(hwmon / "name") or hwmon.name

            for input_path in sorted(hwmon.glob("fan*_input")):
                raw = self._read_text(input_path)
                if raw is None:
                    continue

                try:
                    rpm = int(float(raw))
                except ValueError:
                    continue

                channel = (
                    input_path.name
                    .removeprefix("fan")
                    .removesuffix("_input")
                )
                fans.append(
                    {
                        "channel": int(channel)
                        if channel.isdigit()
                        else channel,
                        "rpm": max(0, rpm),
                        "duty_percent": None,
                        "label": name,
                    }
                )

        if not fans:
            return None

        return {
            "available": True,
            "source": "hwmon",
            "timestamp": time.time(),
            "fans": fans,
        }

    def status(self) -> dict[str, Any]:
        native = self._read_native_snapshot()

        if native is not None:
            if native.get("available"):
                return native
            # A fresh native error is more useful than silently hiding it.
            if native.get("timestamp"):
                return native

        hwmon = self._read_hwmon()
        if hwmon is not None:
            return hwmon

        return {
            "available": False,
            "source": "native-ec",
            "reason": (
                "Native EC telemetry is not available. "
                "Start g6-control-center-telemetry."
            ),
            "fans": [],
        }

    @property
    def available(self) -> bool:
        return bool(self.status().get("available"))


    def set_mode(self, mode: str) -> tuple[bool, str]:
        """Set a global fan profile; both physical fans are changed together."""
        normalized = mode.strip().lower()
        if normalized not in {"quiet", "balanced", "high", "automatic"}:
            return False, "Unsupported fan mode."

        from app.backend.privileges import run_privileged

        result = run_privileged(
            ["fan-mode", normalized],
            timeout=10,
        )
        return result.ok, result.stderr or result.stdout
