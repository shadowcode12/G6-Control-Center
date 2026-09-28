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

    It does not call gigactl. The privileged telemetry service reads the
    G6 KF EC registers and publishes a small read-only JSON snapshot. Kernel
    hwmon fan inputs are preferred when the kernel exposes them.
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

    def _read_hwmon(self) -> dict[str, Any] | None:
        """Use standard hwmon fan RPM if the kernel exposes any."""
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

                channel = input_path.name.removeprefix("fan").removesuffix("_input")
                fans.append(
                    {
                        "channel": int(channel) if channel.isdigit() else channel,
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
        """Return current CPU/GPU fan telemetry."""
        hwmon = self._read_hwmon()
        if hwmon is not None:
            return hwmon

        try:
            payload = json.loads(self.telemetry_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
            return {
                "available": False,
                "source": "native-ec",
                "reason": (
                    "Native EC telemetry is not available. "
                    "Start the g6-control-center-telemetry service."
                ),
                "fans": [],
            }

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

        if not payload.get("available"):
            return payload

        return payload

    @property
    def available(self) -> bool:
        return bool(self.status().get("available"))
