#!/usr/bin/env python3
from __future__ import annotations

import glob
import json
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
        else:
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


def battery_full_charge() -> None:
    end_paths = []
    for pattern in (
        "/sys/class/power_supply/BAT*/charge_control_end_threshold",
        "/sys/class/power_supply/BAT*/charge_stop_threshold",
    ):
        end_paths.extend(glob.glob(pattern))

    if not end_paths:
        raise RuntimeError("Battery charge threshold is not supported.")

    for path in sorted(set(end_paths)):
        write_text(path, "100")

    # Standard charging mode means no custom FlexiCharger thresholds.
    for path in glob.glob("/sys/class/power_supply/BAT*/charge_type"):
        try:
            write_text(path, "Standard")
        except OSError:
            pass


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

def rapl_preset(pl1_watts: float, pl2_watts: float) -> None:
    if pl1_watts <= 0 or pl2_watts <= 0:
        raise ValueError("RAPL limits must be positive.")

    roots = []
    for pattern in (
        "/sys/class/powercap/intel-rapl:*",
        "/sys/class/powercap/intel-rapl-mmio:*",
    ):
        roots.extend(
            path for path in glob.glob(pattern)
            if path.count(":") == 2
        )

    if not roots:
        raise RuntimeError("Intel RAPL is unavailable.")

    chosen: dict[int, str] = {}
    for base in sorted(set(roots)):
        if base.startswith("/sys/class/powercap/intel-rapl:"):
            for index in (0, 1):
                path = os.path.join(
                    base,
                    f"constraint_{index}_power_limit_uw",
                )
                if os.path.exists(path):
                    chosen[index] = path

    # Fall back to the MMIO interface when MSR RAPL is not exposed.
    if len(chosen) < 2:
        for base in sorted(set(roots)):
            for index in (0, 1):
                path = os.path.join(
                    base,
                    f"constraint_{index}_power_limit_uw",
                )
                if os.path.exists(path):
                    chosen.setdefault(index, path)

    if 0 not in chosen or 1 not in chosen:
        raise RuntimeError("Both RAPL PL1 and PL2 controls are unavailable.")

    targets = {
        0: float(pl1_watts),
        1: float(pl2_watts),
    }

    for index, path in chosen.items():
        base = os.path.dirname(path)
        min_path = os.path.join(
            base,
            f"constraint_{index}_min_power_uw",
        )
        max_path = os.path.join(
            base,
            f"constraint_{index}_max_power_uw",
        )

        target_uw = int(round(targets[index] * 1_000_000))

        if os.path.exists(min_path):
            minimum = int(pathlib.Path(min_path).read_text().strip())
            if target_uw < minimum:
                raise ValueError(
                    f"PL{index + 1} is below the kernel minimum."
                )

        if os.path.exists(max_path):
            maximum = int(pathlib.Path(max_path).read_text().strip())
            if target_uw > maximum:
                raise ValueError(
                    f"PL{index + 1} is above the kernel maximum."
                )

        write_text(path, str(target_uw))


def _check_g6_kf() -> None:
    vendor = ""
    product = ""
    for path in (
        "/sys/class/dmi/id/sys_vendor",
        "/sys/class/dmi/id/product_name",
    ):
        try:
            value = pathlib.Path(path).read_text(
                encoding="utf-8",
                errors="ignore",
            ).strip()
        except OSError:
            value = ""

        if path.endswith("sys_vendor"):
            vendor = value
        else:
            product = value

    if vendor.lower() != "gigabyte" or product.upper() != "G6 KF":
        raise RuntimeError(
            "Native EC fan control is restricted to the verified Gigabyte G6 KF."
        )


def _ec_write_byte(handle, offset: int, value: int) -> None:
    handle.seek(offset)
    handle.write(bytes([value & 0xFF]))
    handle.flush()


def _fan_command(handle, fan_number: int, duty: int | None) -> None:
    # G6 KF/Clevo EC fan mailbox:
    # FDAT = 0xF9, FBUF = 0xFA, FCMD/doorbell = 0xF8.
    _ec_write_byte(handle, 0xF9, 0xFF if duty is None else fan_number)
    _ec_write_byte(handle, 0xFA, fan_number if duty is None else duty)
    _ec_write_byte(handle, 0xF8, 0xC1)


def fan_mode(mode: str) -> None:
    _check_g6_kf()

    write_support = "/sys/module/ec_sys/parameters/write_support"
    try:
        value = pathlib.Path(write_support).read_text().strip().upper()
    except OSError as exc:
        raise RuntimeError("ec_sys write support is unavailable.") from exc

    if value not in {"Y", "1"}:
        raise RuntimeError(
            "ec_sys is read-only. Enable ec_sys write support before using fan modes."
        )

    duty_by_mode = {
        "quiet": 45,
        "balanced": 60,
        "high": 100,
        "automatic": None,
    }
    if mode not in duty_by_mode:
        raise ValueError("Unsupported fan mode.")

    ec_path = "/sys/kernel/debug/ec/ec0/io"
    if not os.path.exists(ec_path):
        raise RuntimeError("Linux EC interface is unavailable.")

    import fcntl

    lock_path = "/run/lock/g6-control-center-ec.lock"
    pathlib.Path(lock_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        with open(ec_path, "r+b", buffering=0) as ec:
            duty = duty_by_mode[mode]

            # Never expose independent fan selection in the UI. A mode is a
            # paired thermal profile and applies to both physical fans.
            _fan_command(ec, 1, duty)
            _fan_command(ec, 2, duty)

        pathlib.Path("/run/g6-control-center").mkdir(
            parents=True,
            exist_ok=True,
        )
        pathlib.Path("/run/g6-control-center/fan_mode").write_text(
            mode,
            encoding="utf-8",
        )


KEYBOARD_STATE_DIR = "/var/lib/g6-control-center"
KEYBOARD_STATE_FILE = f"{KEYBOARD_STATE_DIR}/keyboard.json"
EC_PATH = "/sys/kernel/debug/ec/ec0/io"
EC_LOCK_PATH = "/run/lock/g6-control-center-ec.lock"


def _ensure_g6_kf() -> None:
    try:
        vendor = pathlib.Path("/sys/class/dmi/id/sys_vendor").read_text(
            encoding="utf-8",
            errors="ignore",
        ).strip()
        model = pathlib.Path("/sys/class/dmi/id/product_name").read_text(
            encoding="utf-8",
            errors="ignore",
        ).strip()
    except OSError as exc:
        raise RuntimeError("Unable to read DMI hardware identity.") from exc

    if not vendor.lower().startswith("gigabyte"):
        raise RuntimeError("Native keyboard control is restricted to Gigabyte hardware.")
    if model != "G6 KF":
        raise RuntimeError(
            "Native RGB keyboard control is currently hardware-validated only on G6 KF."
        )


def _ec_write_u8(handle, offset: int, value: int) -> None:
    handle.seek(offset)
    handle.write(bytes([int(value) & 0xFF]))
    handle.flush()


def _ec_command(subcommand: int, params: tuple[int, ...], doorbell: int) -> None:
    if not os.path.exists(EC_PATH):
        raise RuntimeError("Linux EC interface is unavailable.")
    try:
        write_support = pathlib.Path(
            "/sys/module/ec_sys/parameters/write_support"
        ).read_text().strip().upper()
    except OSError as exc:
        raise RuntimeError("Could not determine EC write support.") from exc

    if write_support not in {"Y", "1"}:
        raise RuntimeError(
            "EC write support is disabled. Load ec_sys with write support enabled."
        )

    pathlib.Path(EC_LOCK_PATH).parent.mkdir(parents=True, exist_ok=True)

    import fcntl

    with open(EC_LOCK_PATH, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with open(EC_PATH, "r+b", buffering=0) as ec:
            _ec_write_u8(ec, 0xF9, subcommand)
            for offset, value in zip((0xFA, 0xFB, 0xFC, 0xFD), params):
                _ec_write_u8(ec, offset, value)
            _ec_write_u8(ec, 0xF8, doorbell)


def _keyboard_master(enable: bool) -> None:
    # G6 KF: FDAT=0x0C, FBUF=0x3F enables keyboard control;
    # FBUF=0x20 disables it. Doorbell is 0xC4.
    _ec_command(
        0x0C,
        (0x3F if enable else 0x20,),
        0xC4,
    )


def _keyboard_color(r: int, g: int, b: int) -> None:
    # G6 KF is 1-zone RGB and the EC takes B,R,G byte order.
    _ec_command(0x03, (b, r, g), 0xCA)


def _keyboard_brightness(percent: int) -> None:
    level = round(max(0, min(100, percent)) * 255 / 100)
    _ec_command(0x06, (level,), 0xCA)


def _load_keyboard_state() -> dict:
    try:
        return json.loads(
            pathlib.Path(KEYBOARD_STATE_FILE).read_text(
                encoding="utf-8"
            )
        )
    except (
        FileNotFoundError,
        PermissionError,
        OSError,
        json.JSONDecodeError,
    ):
        return {
            "enabled": True,
            "r": 0,
            "g": 0,
            "b": 255,
            "brightness": 100,
        }


def _save_keyboard_state(state: dict) -> None:
    pathlib.Path(KEYBOARD_STATE_DIR).mkdir(
        parents=True,
        exist_ok=True,
    )
    temp = pathlib.Path(KEYBOARD_STATE_FILE + ".tmp")
    temp.write_text(
        json.dumps(state, separators=(",", ":")),
        encoding="utf-8",
    )
    os.chmod(temp, 0o644)
    os.replace(temp, KEYBOARD_STATE_FILE)


def keyboard_color(r: int, g: int, b: int) -> None:
    _ensure_g6_kf()
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))

    state = _load_keyboard_state()
    _keyboard_master(True)
    _keyboard_brightness(int(state.get("brightness", 100)))
    _keyboard_color(r, g, b)

    state.update({
        "enabled": True,
        "r": r,
        "g": g,
        "b": b,
    })
    _save_keyboard_state(state)


def keyboard_brightness(percent: int) -> None:
    _ensure_g6_kf()
    percent = max(0, min(100, int(percent)))

    state = _load_keyboard_state()
    _keyboard_master(True)
    _keyboard_brightness(percent)

    state["brightness"] = percent
    state["enabled"] = True
    _save_keyboard_state(state)


def keyboard_enabled(enabled: bool) -> None:
    _ensure_g6_kf()
    state = _load_keyboard_state()

    if enabled:
        _keyboard_master(True)
        _keyboard_brightness(int(state.get("brightness", 100)))
        _keyboard_color(
            int(state.get("r", 0)),
            int(state.get("g", 0)),
            int(state.get("b", 255)),
        )
        state["enabled"] = True
    else:
        _keyboard_master(False)
        state["enabled"] = False

    _save_keyboard_state(state)


def keyboard_restore() -> None:
    _ensure_g6_kf()
    path = pathlib.Path(KEYBOARD_STATE_FILE)
    if not path.exists():
        return

    state = _load_keyboard_state()

    if bool(state.get("enabled", True)):
        _keyboard_master(True)
        _keyboard_brightness(int(state.get("brightness", 100)))
        _keyboard_color(
            int(state.get("r", 0)),
            int(state.get("g", 0)),
            int(state.get("b", 255)),
        )
    else:
        _keyboard_master(False)


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
        elif action == "battery-full-charge" and len(sys.argv) == 2:
            battery_full_charge()
        elif action == "battery-threshold" and len(sys.argv) == 3:
            battery_threshold(int(sys.argv[2]))
        elif action == "battery-threshold-custom" and len(sys.argv) == 4:
            battery_threshold_custom(int(sys.argv[2]), int(sys.argv[3]))
        elif action == "rapl-preset" and len(sys.argv) == 4:
            rapl_preset(float(sys.argv[2]), float(sys.argv[3]))
        elif action == "fan-mode" and len(sys.argv) == 3:
            fan_mode(sys.argv[2])
        elif action == "keyboard-color" and len(sys.argv) == 5:
            keyboard_color(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
        elif action == "keyboard-brightness" and len(sys.argv) == 3:
            keyboard_brightness(int(sys.argv[2]))
        elif action == "keyboard-enabled" and len(sys.argv) == 3:
            keyboard_enabled(sys.argv[2].lower() == "true")
        elif action == "keyboard-restore" and len(sys.argv) == 2:
            keyboard_restore()
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
