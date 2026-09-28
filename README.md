# G6 Control Center

Linux-native control center for Gigabyte G5/G6-class gaming laptops.

## Current hardware work

- Live CPU, RAM and GPU telemetry.
- Intel GPU telemetry through standard Linux DRM/sysfs interfaces.
- NVIDIA telemetry through nvidia-smi, including graceful handling of driver fields reported as N/A.
- PRIME mode detection and supported switching.
- Live CPU and GPU fan RPM/duty telemetry from the native G6 KF EC path.
- Live battery charge, state, power, voltage/current and health estimates from Linux power-supply sysfs.
- Charge-limit control when the kernel exposes a writable threshold.
- Silent, Balanced, Performance and Gaming system profiles.
- Intel EPP/Turbo and RAPL controls when exposed by the kernel.
- Settings and backend diagnostics.

## G6 KF native backend

The G6 KF is a Clevo-ODM design and exposes a Clevo-style EC command/data layout. This project now owns its hardware telemetry path instead of invoking gigactl.

The native fan telemetry service is read-only in the current stage. It reads the verified G6 KF EC fan/temperature registers through Linux ec_sys and publishes a small local snapshot at:

    /run/g6-control-center/telemetry.json

Manual fan writes are deliberately not exposed yet. The first native stage is telemetry and safety validation; EC writes will only be added after the read path is stable on the target hardware.

RGB EC control is also staged separately and does not use gigactl.

## Installation

For development, create a Python 3.11+ virtual environment and run the project directly.

For a local desktop-style install:

    sudo bash packaging/install.sh

The installer places the application under /opt/g6-control-center, installs the root-owned privileged helper, creates the native telemetry service, installs the desktop entry and launcher, and starts the telemetry service.

## Development

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    pip install pytest
    pytest -q
    python -m app.main

## Hardware boundary

The application does not invoke gigactl.

- GPU monitoring uses NVIDIA's nvidia-smi and standard Intel Linux sysfs/DRM telemetry.
- Fan telemetry uses the kernel EC interface through a small root-owned read-only service.
- CPU controls use Linux power-management interfaces.
- Battery telemetry uses /sys/class/power_supply.
- Privileged control operations use a fixed-action root-owned helper through PolicyKit.
- EC writes are intentionally not enabled in the fan telemetry stage.

## Safety

Power limits and Turbo can affect thermals, performance and battery life. The app validates values against kernel/driver-exposed ranges where available.

Fan telemetry is read-only in the current native backend. This prevents a bad control write from leaving the EC in an unknown state while the register map is being validated.

## License

MIT
