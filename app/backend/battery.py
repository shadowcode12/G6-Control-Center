from __future__ import annotations

from pathlib import Path
import glob

from app.backend.privileges import run_privileged


class BatteryController:
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

    def status(self) -> dict:
        base = self._battery_dir()
        if base is None:
            return {"available": False}

        capacity = self._read(base / "capacity")
        state = self._read(base / "status")
        threshold = self._read(base / "charge_control_end_threshold")
        energy_full = self._read(base / "energy_full")
        energy_design = self._read(base / "energy_full_design")

        health = None
        if energy_full and energy_design:
            try:
                full = float(energy_full)
                design = float(energy_design)
                if design > 0:
                    health = full / design * 100
            except ValueError:
                pass

        return {
            "available": True,
            "name": base.name,
            "capacity": int(capacity) if capacity and capacity.isdigit() else None,
            "state": state,
            "charge_limit": int(threshold) if threshold and threshold.isdigit() else None,
            "health": health,
        }

    def supports_limit(self) -> bool:
        base = self._battery_dir()
        return bool(base and (base / "charge_control_end_threshold").exists())

    def set_limit(self, percent: int) -> tuple[bool, str]:
        value = max(50, min(100, int(percent)))
        result = run_privileged(["battery-threshold", str(value)], timeout=10)
        return result.ok, result.stderr or result.stdout
