# Architecture

G6 Control Center is a PySide6 GUI with isolated backend adapters.

## Layers

`app/ui` contains presentation only.
`app/backend` talks to Linux, NVIDIA and gigactl interfaces.
`app/services` contains fixed-action privileged operations.

## Hardware boundary

The application does not write Gigabyte/Clevo EC registers directly.
Fan and RGB operations go through the gigactl CLI/daemon, preserving its G6 KF model guard.
CPU controls use powerprofilesctl, cpufreq/Intel pstate and Intel RAPL when available.
NVIDIA controls use nvidia-smi and prime-select when available.

## Privilege model

Only a small allow-listed helper is executed through pkexec.
Supported privileged actions are Turbo, EPP, battery threshold, RAPL limit, NVIDIA power limit and PRIME mode.
Values are validated before writes; arbitrary sysfs paths are never accepted.

## Roadmap

Background workers, tray controls, game profiles, richer graphs and packaging are the next milestones.