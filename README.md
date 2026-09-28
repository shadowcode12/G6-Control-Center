# G6 Control Center

Linux-native control center for Gigabyte G5/G6-class gaming laptops.

## Features

- Live CPU, RAM and NVIDIA GPU monitoring.
- Silent, Balanced, Performance and Gaming system profiles.
- Intel EPP and Turbo controls when exposed by the kernel.
- Intel RAPL power-limit controls when exposed.
- NVIDIA GPU power-limit controls when exposed.
- PRIME mode switching on supported Ubuntu NVIDIA installations.
- Fan and single-zone RGB control through gigactl.
- Battery status, health estimate and charge-limit control when exposed.
- Settings and backend diagnostics.

## Hardware boundary

The app never writes Gigabyte/Clevo EC registers directly. Fan and RGB EC operations are delegated to gigactl.
CPU controls use standard Linux power-management interfaces. NVIDIA controls use nvidia-smi and PRIME when available.
Privileged operations are restricted to a fixed-action helper and PolicyKit.

## Development

Use a Python 3.11+ virtual environment, install the project in editable mode, run pytest, then start with python -m app.main.

## Safety

Power limits and Turbo can affect thermals and battery life. The app validates values against kernel/driver-exposed ranges where available.
Manual fan control is delegated to gigactl and can be returned to firmware auto.

## License

MIT