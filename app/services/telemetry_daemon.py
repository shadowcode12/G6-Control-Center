from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import time

from app.backend.embedded_controller import EmbeddedController, EmbeddedControllerError


OUTPUT_DIR = Path("/run/g6-control-center")
OUTPUT_FILE = OUTPUT_DIR / "telemetry.json"
POLL_SECONDS = 0.5

CPU_TEMP = 0x07
GPU_TEMP = 0x0A
DUTY_FAN1 = 0xCE
DUTY_FAN2 = 0xCF
TACH1_HI, TACH1_LO = 0xD0, 0xD1
TACH2_HI, TACH2_LO = 0xD2, 0xD3
RPM_CONST = 2_156_220
STOPPED_AT = 0xFF00


_running = True


def _stop(*_args: object) -> None:
    global _running
    _running = False


def _rpm(period: int) -> int:
    if period <= 0 or period >= STOPPED_AT:
        return 0
    return RPM_CONST // period


def _duty(raw: int) -> int:
    return max(0, min(100, raw * 100 // 255))


def read_snapshot(ec: EmbeddedController) -> dict:
    try:
        cpu = ec.read_u8(CPU_TEMP)
        gpu = ec.read_u8(GPU_TEMP)
        duty1 = ec.read_u8(DUTY_FAN1)
        duty2 = ec.read_u8(DUTY_FAN2)
        period1 = ec.read_u16_be(TACH1_HI, TACH1_LO)
        period2 = ec.read_u16_be(TACH2_HI, TACH2_LO)

        return {
            "available": True,
            "source": "native-ec",
            "timestamp": time.time(),
            "cpu_temperature_c": cpu,
            "gpu_temperature_c": gpu,
            "fans": [
                {
                    "channel": 1,
                    "label": "CPU Fan",
                    "rpm": _rpm(period1),
                    "duty_percent": _duty(duty1),
                },
                {
                    "channel": 2,
                    "label": "GPU Fan",
                    "rpm": _rpm(period2),
                    "duty_percent": _duty(duty2),
                },
            ],
        }
    except (EmbeddedControllerError, OSError, ValueError) as exc:
        return {
            "available": False,
            "source": "native-ec",
            "timestamp": time.time(),
            "reason": str(exc),
            "fans": [],
        }


def write_snapshot(payload: dict) -> None:
    OUTPUT_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = OUTPUT_FILE.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    os.chmod(temporary, 0o644)
    os.replace(temporary, OUTPUT_FILE)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("The native telemetry service must run as root.")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    ec = EmbeddedController()

    while _running:
        write_snapshot(read_snapshot(ec))
        time.sleep(POLL_SECONDS)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
