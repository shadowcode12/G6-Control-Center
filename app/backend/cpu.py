from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import glob
import time
from typing import Any

from app.backend.performance import CommandResult, PerformanceController
from app.backend.privileges import run_privileged
from app.backend.system_info import get_cpu_temperature


@dataclass(frozen=True)
class RaplConstraint:
    index: int
    name: str
    current_watts: float
    minimum_watts: float | None
    maximum_watts: float | None
    path: str


class CpuController:
    """
    Dedicated CPU telemetry/control facade.

    User-facing CPU controls are intentionally limited to:
      - live CPU telemetry
      - Turbo Boost
      - three-level Energy Performance Preference
      - optional, preset-only RAPL controls when the kernel exposes them

    No arbitrary voltage/overclock controls are exposed.
    """

    EPP_OPTIONS = ("power", "balance_power", "performance")
    EPP_LABELS = {
        "power": "Low",
        "balance_power": "Mid",
        "performance": "High",
    }

    # These are platform-oriented presets for the i7-13620H/G6 KF. Every value
    # is clamped to the live kernel-exposed range before a write.
    RAPL_PRESETS = {
        "low": (35.0, 80.0),
        "mid": (45.0, 115.0),
        "high": (55.0, 115.0),
    }

    def __init__(self) -> None:
        self.performance = PerformanceController()
        self._last_energy_uj: float | None = None
        self._last_energy_time: float | None = None

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    def _package_paths(self) -> list[Path]:
        paths = []
        for pattern in (
            "/sys/class/powercap/intel-rapl:*",
            "/sys/class/powercap/intel-rapl-mmio:*",
        ):
            paths.extend(Path(p) for p in glob.glob(pattern))

        # Only package roots, not nested :0:0 domains.
        return sorted(
            path for path in set(paths)
            if path.name.count(":") == 1
        )

    def rapl_supported(self) -> bool:
        return bool(self._package_paths())

    def rapl_constraints(self) -> list[RaplConstraint]:
        result: list[RaplConstraint] = []

        for base in self._package_paths():
            for index in (0, 1):
                current_path = base / f"constraint_{index}_power_limit_uw"
                if not current_path.exists():
                    continue

                raw = self._read(current_path)
                if raw is None:
                    continue

                try:
                    current = float(raw) / 1_000_000.0
                except ValueError:
                    continue

                minimum = self._read(
                    base / f"constraint_{index}_min_power_uw"
                )
                maximum = self._read(
                    base / f"constraint_{index}_max_power_uw"
                )
                name = self._read(
                    base / f"constraint_{index}_name"
                ) or ("PL1" if index == 0 else "PL2")

                try:
                    min_watts = (
                        float(minimum) / 1_000_000.0
                        if minimum is not None
                        else None
                    )
                except ValueError:
                    min_watts = None

                try:
                    max_watts = (
                        float(maximum) / 1_000_000.0
                        if maximum is not None
                        else None
                    )
                except ValueError:
                    max_watts = None

                result.append(
                    RaplConstraint(
                        index=index,
                        name=name,
                        current_watts=current,
                        minimum_watts=min_watts,
                        maximum_watts=max_watts,
                        path=str(base),
                    )
                )

        # Prefer MSR RAPL over MMIO when both are exposed for the same index.
        preferred: dict[int, RaplConstraint] = {}
        for item in result:
            if item.path.startswith("/sys/class/powercap/intel-rapl:"):
                preferred[item.index] = item
            else:
                preferred.setdefault(item.index, item)

        return [preferred[i] for i in sorted(preferred)]

    @staticmethod
    def _clamp(value: float, item: RaplConstraint) -> float:
        if item.minimum_watts is not None:
            value = max(value, item.minimum_watts)
        if item.maximum_watts is not None:
            value = min(value, item.maximum_watts)
        return value

    def rapl_preset(self, name: str) -> dict[str, float] | None:
        targets = self.RAPL_PRESETS.get(name.lower())
        if targets is None:
            return None

        constraints = self.rapl_constraints()
        by_index = {item.index: item for item in constraints}
        if 0 not in by_index or 1 not in by_index:
            return None

        pl1 = self._clamp(targets[0], by_index[0])
        pl2 = self._clamp(targets[1], by_index[1])

        return {
            "pl1": pl1,
            "pl2": pl2,
        }

    def set_rapl_preset(self, name: str) -> CommandResult:
        preset = self.rapl_preset(name)
        if preset is None:
            return CommandResult(
                ok=False,
                stderr=(
                    "RAPL preset is unavailable because the kernel did not "
                    "expose writable PL1 and PL2 constraints."
                ),
                returncode=95,
            )

        result = run_privileged(
            [
                "rapl-preset",
                f"{preset['pl1']:.3f}",
                f"{preset['pl2']:.3f}",
            ],
            timeout=10,
        )

        return CommandResult(
            ok=result.ok,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def telemetry(self) -> dict[str, Any]:
        energy_paths = [
            Path(base) / "energy_uj"
            for base in (
                "/sys/class/powercap/intel-rapl:0",
                "/sys/class/powercap/intel-rapl-mmio:0",
            )
            if Path(base, "energy_uj").exists()
        ]

        package_power = None

        if energy_paths:
            raw = self._read(energy_paths[0])
            try:
                now_energy = float(raw) if raw is not None else None
            except ValueError:
                now_energy = None

            now_time = time.monotonic()

            if (
                now_energy is not None
                and self._last_energy_uj is not None
                and self._last_energy_time is not None
            ):
                delta_energy = now_energy - self._last_energy_uj

                max_raw = self._read(
                    energy_paths[0].parent / "max_energy_range_uj"
                )
                try:
                    max_energy = (
                        float(max_raw)
                        if max_raw is not None
                        else None
                    )
                except ValueError:
                    max_energy = None

                if (
                    delta_energy < 0
                    and max_energy is not None
                ):
                    delta_energy += max_energy

                delta_time = now_time - self._last_energy_time
                if delta_time > 0 and delta_energy >= 0:
                    package_power = delta_energy / 1_000_000.0 / delta_time

            if now_energy is not None:
                self._last_energy_uj = now_energy
                self._last_energy_time = now_time

        epp = self.performance.energy_performance_preference()

        return {
            "usage": None,
            "temperature": get_cpu_temperature(),
            "frequency_mhz": self._average_frequency(),
            "package_power_w": package_power,
            "turbo": self.performance.turbo_enabled(),
            "epp": epp,
            "driver": self.performance.cpu_driver(),
            "rapl_supported": self.rapl_supported(),
            "rapl": self.rapl_constraints(),
        }

    @classmethod
    def _average_frequency(cls) -> float | None:
        values: list[float] = []

        for path in Path("/sys/devices/system/cpu").glob(
            "cpu[0-9]*/cpufreq/scaling_cur_freq"
        ):
            raw = cls._read(path)
            if raw is None:
                continue
            try:
                values.append(float(raw) / 1000.0)
            except ValueError:
                continue

        if not values:
            return None

        return sum(values) / len(values)

    def turbo_enabled(self) -> bool | None:
        return self.performance.turbo_enabled()

    def set_turbo_enabled(self, enabled: bool) -> CommandResult:
        result = self.performance.set_turbo_enabled(enabled)
        return result

    def energy_preference(self) -> str | None:
        return self.performance.energy_performance_preference()

    def set_energy_preference(self, value: str) -> CommandResult:
        return self.performance.set_epp(value)
