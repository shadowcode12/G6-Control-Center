from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from app.backend.privileges import run_privileged


THRESHOLD_FILES = (
    "charge_control_end_threshold",
    "charge_stop_threshold",
)


class BatteryController:
    """Linux power-supply battery telemetry and charge-limit adapter."""

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

    def _threshold_path(self, base: Path) -> Path | None:
        for name in THRESHOLD_FILES:
            path = base / name
            if path.exists():
                return path
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
        state = self._read(base / "status")

        try:
            capacity = int(float(capacity_raw)) if capacity_raw is not None else None
        except ValueError:
            capacity = None

        charge_now = self._number(base, "charge_now")
        charge_full = self._number(base, "charge_full", "energy_full")
        charge_design = self._number(
            base,
            "charge_full_design",
            "energy_full_design",
        )
        energy_now = self._number(base, "energy_now")
        energy_full = self._number(base, "energy_full")
        energy_design = self._number(base, "energy_full_design")

        full = charge_full if charge_full is not None else energy_full
        design = charge_design if charge_design is not None else energy_design

        health = None
        if full is not None and design is not None and design > 0:
            health = max(0.0, min(100.0, full / design * 100.0))

        voltage = self._number(base, "voltage_now")
        current = self._number(base, "current_now")
        power_mw = self._number(base, "power_now")

        voltage_v = voltage / 1_000_000 if voltage is not None else None
        current_a = current / 1_000_000 if current is not None else None
        power_w = power_mw / 1_000_000 if power_mw is not None else None

        if power_w is None and voltage_v is not None and current_a is not None:
            power_w = abs(voltage_v * current_a)

        threshold_path = self._threshold_path(base)
        threshold_raw = self._read(threshold_path) if threshold_path else None

        try:
            charge_limit = int(float(threshold_raw)) if threshold_raw is not None else None
        except ValueError:
            charge_limit = None

        time_remaining_minutes = None
        watts_for_eta = power_w if power_w and power_w > 0.1 else None

        if state and watts_for_eta:
            energy = energy_now
            full_energy = energy_full
            if state.lower() == "discharging" and energy is not None:
                time_remaining_minutes = max(0.0, energy / (watts_for_eta * 1_000_000) * 60)
            elif state.lower() in {"charging", "not charging"}:
                if energy is not None and full_energy is not None and full_energy > energy:
                    time_remaining_minutes = max(
                        0.0,
                        (full_energy - energy) / (watts_for_eta * 1_000_000) * 60,
                    )

        return {
            "available": True,
            "name": base.name,
            "capacity": capacity,
            "state": state,
            "health": health,
            "charge_limit": charge_limit,
            "supports_limit": threshold_path is not None,
            "voltage_v": voltage_v,
            "current_a": current_a,
            "power_w": power_w,
            "time_remaining_minutes": time_remaining_minutes,
            "charger_connected": self._charger_connected(),
            "energy_now": energy_now,
            "energy_full": energy_full,
            "energy_design": energy_design,
            "charge_now": charge_now,
            "charge_full": charge_full,
            "charge_design": charge_design,
        }

    def supports_limit(self) -> bool:
        base = self._battery_dir()
        return bool(base and self._threshold_path(base))

    def set_limit(self, percent: int) -> tuple[bool, str]:
        base = self._battery_dir()
        if base is None:
            return False, "No battery device detected."

        if not self._threshold_path(base):
            return False, (
                "Battery charge-limit control is not exposed by this "
                "laptop/kernel."
            )

        value = max(50, min(100, int(percent)))
        result = run_privileged(
            ["battery-threshold", str(value)],
            timeout=10,
        )
        return result.ok, result.stderr or result.stdout
