#!/usr/bin/env python3
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys


ALLOWED_EPP = {
    "performance",
    "balance_performance",
    "balance_power",
    "power",
}


def require_root() -> None:
    if os.geteuid() != 0:
        print("This helper must run as root.", file=sys.stderr)
        raise SystemExit(13)


def write_text(path: str, value: str) -> None:
    pathlib.Path(path).write_text(value, encoding="utf-8")


def set_turbo(enabled: bool) -> None:
    candidates = [
        "/sys/devices/system/cpu/intel_pstate/no_turbo",
        "/sys/devices/system/cpu/cpufreq/boost",
    ]

    for path in candidates:
        if not os.path.exists(path):
            continue

        if path.endswith("no_turbo"):
            write_text(path, "0" if enabled else "1")
            return

        # cpufreq boost uses 1 for enabled and 0 for disabled.
        write_text(path, "1" if enabled else "0")
        return

    raise RuntimeError("No supported Turbo Boost control was found.")


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

    paths: list[str] = []
    for pattern in (
        "/sys/class/power_supply/BAT*/charge_control_end_threshold",
        "/sys/class/power_supply/BAT*/charge_stop_threshold",
    ):
        paths.extend(glob.glob(pattern))

    paths = sorted(set(paths))
    if not paths:
        raise RuntimeError("Battery charge threshold is not supported.")

    for path in paths:
        write_text(path, str(value))

def rapl_power_limit(constraint: int, watts: float) -> None:
    if constraint not in (0, 1):
        raise ValueError("Only RAPL constraints 0 and 1 are supported.")

    base_dirs = glob.glob("/sys/class/powercap/intel-rapl:*")
    if not base_dirs:
        raise RuntimeError("Intel RAPL is unavailable.")

    written = False

    for base in base_dirs:
        limit_path = os.path.join(
            base, f"constraint_{constraint}_power_limit_uw"
        )
        if not os.path.exists(limit_path):
            continue

        min_path = os.path.join(
            base, f"constraint_{constraint}_min_power_uw"
        )
        max_path = os.path.join(
            base, f"constraint_{constraint}_max_power_uw"
        )

        minimum = int(pathlib.Path(min_path).read_text()) if os.path.exists(min_path) else 0
        maximum = int(pathlib.Path(max_path).read_text()) if os.path.exists(max_path) else 10**9
        micro_watts = int(round(watts * 1_000_000))

        if not minimum <= micro_watts <= maximum:
            raise ValueError(
                f"Requested limit is outside the firmware/kernel range "
                f"({minimum / 1_000_000:.2f}-{maximum / 1_000_000:.2f} W)."
            )

        write_text(limit_path, str(micro_watts))
        written = True

    if not written:
        raise RuntimeError("Requested RAPL constraint is unavailable.")


def gpu_power_limit(watts: float) -> None:
    if watts <= 0:
        raise ValueError("GPU power limit must be positive.")

    query = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=power.min_limit,power.max_limit",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if query.returncode != 0:
        raise RuntimeError(
            query.stderr.strip() or "Could not read NVIDIA power limits."
        )

    values = [item.strip() for item in query.stdout.strip().split(",")]
    if len(values) >= 2:
        try:
            minimum = float(values[0])
            maximum = float(values[1])
            if not minimum <= watts <= maximum:
                raise ValueError(
                    f"GPU power limit must be between {minimum:.1f} and {maximum:.1f} W."
                )
        except ValueError as exc:
            if "between" in str(exc):
                raise
            raise RuntimeError("NVIDIA returned an invalid power-limit range.")

    result = subprocess.run(
        ["nvidia-smi", "--power-limit", str(watts)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or "nvidia-smi could not set the power limit."
        )


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
        if action == "turbo" and len(sys.argv) == 3:
            set_turbo(sys.argv[2] == "on")
        elif action == "epp" and len(sys.argv) == 3:
            set_epp(sys.argv[2])
        elif action == "battery-threshold" and len(sys.argv) == 3:
            battery_threshold(int(sys.argv[2]))
        elif action == "rapl" and len(sys.argv) == 4:
            rapl_power_limit(int(sys.argv[2]), float(sys.argv[3]))
        elif action == "gpu-power-limit" and len(sys.argv) == 3:
            gpu_power_limit(float(sys.argv[2]))
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
