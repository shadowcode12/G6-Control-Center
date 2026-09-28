# G6 Control Center

Linux-native control center for Gigabyte G5/G6-class gaming laptops.

## Current hardware features

- Live CPU, RAM and Intel/NVIDIA GPU telemetry.
- NVIDIA default GPU power/TGP reported as read-only information; no GPU power-limit, overclocking or undervolting controls.
- PRIME mode detection and switching on supported Ubuntu NVIDIA installations.
- Live CPU/GPU fan RPM and EC duty telemetry through the native G6 KF EC reader.
- Per-fan manual writes are intentionally not exposed.
- Live battery charge, state, voltage/current, power and health telemetry.
- Full Charge, Locked at 80% and Custom charging modes when the Linux battery driver exposes the corresponding threshold interfaces.
- Simple CPU Energy Preference: Low / Mid / High.
- System performance profiles: Silent / Balanced / Performance / Gaming.

## G6 KF hardware policy

The G6 KF firmware exposes a number of controls differently from desktop platforms. This application therefore treats CPU/GPU power limits, voltage controls, overclocking and per-fan manual control as unavailable features rather than pretending software can safely override the firmware.

The native EC telemetry service is read-only. It reads the verified G6 KF EC temperature, fan-duty and tachometer registers and publishes a short-lived snapshot at `/run/g6-control-center/telemetry.json`.

Battery charging uses standard Linux power-supply threshold interfaces when the active battery driver provides them. Clevo-family FlexiCharger support on Linux depends on a compatible `clevo_acpi` driver exposing those interfaces; not every Clevo-based machine exposes them. Linux's standard `charge_control_*` interface defines `Custom` charging as the mode that uses start/stop thresholds. citeturn592304search0turn318739search5

## Installation

    chmod +x packaging/install.sh
    sudo ./packaging/install.sh

The installer installs the application, privileged helper, native telemetry service and desktop launcher. It also probes the optional `clevo_acpi` kernel module when the running kernel provides it.

## Development

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    pip install pytest
    pytest -q
    python -m app.main

## Hardware boundary

The application does not invoke gigactl or other third-party hardware control CLIs.

- GPU telemetry: `nvidia-smi` and Intel DRM/sysfs.
- Fan telemetry: native EC read service.
- Battery telemetry: `/sys/class/power_supply`.
- CPU profiles/EPP: standard Linux interfaces.
- Privileged writes: fixed allow-listed PolicyKit helper.
- EC control writes: deliberately not enabled in the telemetry stage.

## License

MIT
