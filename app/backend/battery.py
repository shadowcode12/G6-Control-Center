from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from app.backend.privileges import run_privileged


START_THRESHOLD_FILES = (
    "charge_control_start_threshold",
    "charge_start_threshold",
)

END_THRESHOLD_FILES = (
    "charge_control_end_threshold",
    "charge_stop_threshold",
)

CHARGE_TYPE_FILE = "charge_type"

# Common Clevo/Tuxedo-style FlexiCharger values when a supported driver exposes
# the full start/stop interface. The backend still reads the actual sysfs files
# so arbitrary values are never claimed unless the kernel accepts them.
CLEVO_START_VALUES = (40, 50, 60, 70, 80, 95)
CLEVO_END_VALUES = (60, 70, 80, 90, 100)


class BatteryController:
    """Live Linux battery telemetry and threshold control."""

    CLEVO_START_VALUES = CLEVO_START_VALUES
    CLEVO_END_VALUES = CLEVO_END_VALUES

    def _battery_dir(self) -> Path | None:
        batteries = sorted(glob.glob("/sys/class/power_supply/BAT*"))
        return Path(batteries[0]) if batteries else None

    @property
    def available(self) -> bool:
        return self._battery_dir() is not None

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    @classmethod
    def _number(cls, base: Path, *names: str) -> float | None:
        for name in names:
            raw = cls._read(base / name)
            if raw is None:
                continue
            try:
                return float(raw)
            except ValueError:
                continue
        return None

    def _find_file(self, base: Path, names: tuple[str, ...]) -> Path | None:
        for name in names:
            candidate = base / name
            if candidate.exists():
                return candidate
        return None

    def _charger_connected(self) -> bool | None:
        found = False
        for supply in sorted(Path("/sys/class/power_supply").glob("*")):
            if supply.name.startswith("BAT"):
                continue
            online = self._read(supply / "online")
            if online is None:
                continue
            found = True
            if online == "1":
                return True
        return False if found else None

    def status(self) -> dict[str, Any]:
        base = self._battery_dir()
        if base is None:
            return {
                "available": False,
                "reason": "No battery device detected.",
            }

        capacity_raw = self._read(base / "capacity")
        try:
            capacity = int(float(capacity_raw)) if capacity_raw is not None else None
        except ValueError:
            capacity = None

        state = self._read(base / "status")
        charge_now = self._number(base, "charge_now")
        charge_full = self._number(base, "charge_full")
        charge_design = self._number(base, "charge_full_design")
        energy_now = self._number(base, "energy_now")
        energy_full = self._number(base, "energy_full")
        energy_design = self._number(base, "energy_full_design")

        full = charge_full if charge_full is not None else energy_full
        design = charge_design if charge_design is not None else energy_design
        health = (
            max(0.0, min(100.0, full / design * 100.0))
            if full is not None and design is not None and design > 0
            else None
        )

        voltage = self._number(base, "voltage_now")
        current = self._number(base, "current_now")
        power_raw = self._number(base, "power_now")

        voltage_v = voltage / 1_000_000 if voltage is not None else None
        current_a = current / 1_000_000 if current is not None else None
        power_w = power_raw / 1_000_000 if power_raw is not None else None

        if power_w is None and voltage_v is not None and current_a is not None:
            power_w = abs(voltage_v * current_a)

        start_path = self._find_file(base, START_THRESHOLD_FILES)
        end_path = self._find_file(base, END_THRESHOLD_FILES)
        charge_type = self._read(base / CHARGE_TYPE_FILE)

        driver_name = None
        try:
            driver_link = base.joinpath("device", "driver")
            if driver_link.exists():
                driver_name = driver_link.resolve().name
        except OSError:
            driver_name = None

        try:
            start = int(float(self._read(start_path))) if start_path else None
        except (TypeError, ValueError):
            start = None

        try:
            end = int(float(self._read(end_path))) if end_path else None
        except (TypeError, ValueError):
            end = None

        custom_supported = start_path is not None and end_path is not None
        end_only_supported = end_path is not None

        # Clevo/Tuxedo-style drivers expose charge_type=Custom when thresholds
        # are active. Standard power-supply semantics define Custom as the mode
        # which uses charge_control_* thresholds.
        time_remaining_minutes = None
        if state and power_w and power_w > 0.1:
            state_lower = state.lower()

            if state_lower == "discharging":
                if energy_now is not None:
                    time_remaining_minutes = max(
                        0.0,
                        energy_now / (power_w * 1_000_000) * 60,
                    )
                elif (
                    charge_now is not None
                    and current_a is not None
                    and current_a > 0.05
                ):
                    time_remaining_minutes = max(
                        0.0,
                        charge_now / 1_000_000.0 / current_a * 60,
                    )

            elif state_lower == "charging":
                if (
                    energy_now is not None
                    and energy_full is not None
                    and energy_full > energy_now
                ):
                    time_remaining_minutes = max(
                        0.0,
                        (energy_full - energy_now)
                        / (power_w * 1_000_000)
                        * 60,
                    )
                elif (
                    charge_now is not None
                    and charge_full is not None
                    and current_a is not None
                    and current_a > 0.05
                    and charge_full > charge_now
                ):
                    time_remaining_minutes = max(
                        0.0,
                        (charge_full - charge_now)
                        / 1_000_000.0
                        / current_a
                        * 60,
                    )

        return {
            "available": True,
            "name": base.name,
            "capacity": capacity,
            "state": state,
            "health": health,
            "charger_connected": self._charger_connected(),
            "voltage_v": voltage_v,
            "current_a": current_a,
            "power_w": power_w,
            "time_remaining_minutes": time_remaining_minutes,
            "charge_now": charge_now,
            "charge_full": charge_full,
            "charge_design": charge_design,
            "energy_now": energy_now,
            "energy_full": energy_full,
            "energy_design": energy_design,
            "charge_type": charge_type,
            "driver": driver_name,
            "charge_limit": end,
            "charge_start": start,
            "supports_limit": end_only_supported,
            "supports_custom": custom_supported,
            "start_values": CLEVO_START_VALUES,
            "end_values": CLEVO_END_VALUES,
        }

    def supports_limit(self) -> bool:
        base = self._battery_dir()
        return bool(base and self._find_file(base, END_THRESHOLD_FILES))

    def supports_custom(self) -> bool:
        base = self._battery_dir()
        return bool(
            base
            and self._find_file(base, START_THRESHOLD_FILES)
            and self._find_file(base, END_THRESHOLD_FILES)
        )

    def set_full_charge(self) -> tuple[bool, str]:
        base = self._battery_dir()
        if base is None:
            return False, "No battery device detected."
        end_path = self._find_file(base, END_THRESHOLD_FILES)
        if end_path is None:
            return False, "Full-charge control is not exposed by the Linux battery driver."
        result = run_privileged(["battery-full-charge"], timeout=10)
        return result.ok, result.stderr or result.stdout

    def set_limit(self, percent: int, start_percent: int | None = None) -> tuple[bool, str]:
        base = self._battery_dir()
        if base is None:
            return False, "No battery device detected."

        end_path = self._find_file(base, END_THRESHOLD_FILES)
        if end_path is None:
            return False, (
                "Battery charge-limit control is not exposed by the "
                "current Linux battery driver."
            )

        end_percent = max(1, min(100, int(percent)))

        if start_percent is None:
            # Single-threshold drivers only need an end value.
            result = run_privileged(
                ["battery-threshold", str(end_percent)],
                timeout=10,
            )
        else:
            start_path = self._find_file(base, START_THRESHOLD_FILES)
            if start_path is None:
                return False, "Custom start/stop charging is not exposed by the kernel."

            start = max(1, min(99, int(start_percent)))
            if start >= end_percent:
                return False, "Start threshold must be lower than stop threshold."

            result = run_privileged(
                ["battery-threshold-custom", str(start), str(end_percent)],
                timeout=10,
            )

        return result.ok, result.stderr or result.stdout
