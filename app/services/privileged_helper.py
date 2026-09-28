#!/usr/bin/env python3
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys


ALLOWED_EPP = {
    "performance",
    "balance_power",
    "power",
}


def require_root() -> None:
    if os.geteuid() != 0:
        print("This helper must run as root.", file=sys.stderr)
        raise SystemExit(13)


def write_text(path: str, value: str) -> None:
    pathlib.Path(path).write_text(value, encoding="utf-8")


def set_epp(value: str) -> None:
    if value not in ALLOWED_EPP:
        raise ValueError(f"Unsupported EPP value: {value}")

    paths = glob.glob(
        "/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"
    )
    if not paths:
        raise RuntimeError("Energy Performance Preference is unavailable.")

    for path in paths:
        if os.path.exists(path):
            write_text(path, value)


def battery_threshold(value: int) -> None:
    if not 50 <= value <= 100:
        raise ValueError("Battery threshold must be between 50 and 100.")

    paths = []
    for pattern in (
        "/sys/class/power_supply/BAT*/charge_control_end_threshold",
        "/sys/class/power_supply/BAT*/charge_stop_threshold",
    ):
        paths.extend(glob.glob(pattern))

    if not paths:
        raise RuntimeError("Battery charge threshold is not supported.")

    for path in sorted(set(paths)):
        write_text(path, str(value))


def battery_threshold_custom(start: int, end: int) -> None:
    if not 1 <= start <= 99:
        raise ValueError("Start threshold must be between 1 and 99.")
    if not 1 <= end <= 100:
        raise ValueError("Stop threshold must be between 1 and 100.")
    if start >= end:
        raise ValueError("Start threshold must be lower than stop threshold.")

    start_paths = []
    for pattern in (
        "/sys/class/power_supply/BAT*/charge_control_start_threshold",
        "/sys/class/power_supply/BAT*/charge_start_threshold",
    ):
        start_paths.extend(glob.glob(pattern))

    end_paths = []
    for pattern in (
        "/sys/class/power_supply/BAT*/charge_control_end_threshold",
        "/sys/class/power_supply/BAT*/charge_stop_threshold",
    ):
        end_paths.extend(glob.glob(pattern))

    if not start_paths or not end_paths:
        raise RuntimeError("Custom battery charging thresholds are not supported.")

    for path in sorted(set(start_paths)):
        write_text(path, str(start))
    for path in sorted(set(end_paths)):
        write_text(path, str(end))

    # Some Clevo-family drivers require Custom charging mode to use the
    # configured thresholds. Only touch this standard power-supply attribute
    # when it is actually exposed.
    for pattern in ("/sys/class/power_supply/BAT*/charge_type",):
        for path in glob.glob(pattern):
            try:
                write_text(path, "Custom")
            except OSError:
                pass

def prime_mode(mode: str) -> None:
    if mode not in {"intel", "on-demand", "nvidia"}:
        raise ValueError("Unsupported PRIME mode.")

    result = subprocess.run(
        ["prime-select", mode],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "prime-select failed."
        )


def main() -> int:
    require_root()

    if len(sys.argv) < 2:
        print("Missing action.", file=sys.stderr)
        return 2

    action = sys.argv[1]

    try:
        if action == "epp" and len(sys.argv) == 3:
            set_epp(sys.argv[2])
        elif action == "battery-threshold" and len(sys.argv) == 3:
            battery_threshold(int(sys.argv[2]))
        elif action == "battery-threshold-custom" and len(sys.argv) == 4:
            battery_threshold_custom(int(sys.argv[2]), int(sys.argv[3]))
        elif action == "prime-mode" and len(sys.argv) == 3:
            prime_mode(sys.argv[2])
        else:
            print("Invalid action or arguments.", file=sys.stderr)
            return 2
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
