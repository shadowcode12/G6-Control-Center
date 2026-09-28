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

## G6 KF focus

The project is developed and tested around the Gigabyte G6 KF. Its fan and keyboard EC operations are delegated to gigactl rather than reimplementing EC register writes.

## Installation

For development, create a Python 3.11+ virtual environment and run the project directly.

For a local desktop-style install, run:

    sudo bash packaging/install.sh

This installs the application under /opt/g6-control-center, a trusted root-owned privileged helper, a desktop entry, and a g6-control-center launcher.

## Development

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    pip install pytest
    pytest -q
    python -m app.main

## Hardware boundary

The app never writes Gigabyte or Clevo EC registers directly. Fan and RGB operations go through gigactl.
CPU controls use standard Linux power-management interfaces. NVIDIA controls use nvidia-smi and prime-select when available.
Privileged operations use a fixed-action root-owned helper through PolicyKit.

## Safety

Power limits and Turbo can affect thermals, performance and battery life. The app validates values against kernel/driver-exposed ranges where available.
Manual fan control is delegated to gigactl and can be returned to firmware auto.

## License

MIT
