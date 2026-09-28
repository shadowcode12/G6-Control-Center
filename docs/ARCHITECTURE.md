# Architecture

G6 Control Center is a PySide6 GUI with isolated Linux hardware adapters.

## Layers

app/ui contains presentation only.

app/backend talks to Linux sysfs/DRM, NVIDIA, the native EC telemetry snapshot and power-management interfaces.

app/services contains fixed-action privileged operations and the native root-owned telemetry service.

## GPU telemetry

The graphics layer combines:

- NVIDIA telemetry from nvidia-smi
- Intel GPU telemetry from DRM/sysfs

PRIME mode is used to choose the preferred GPU for the live GPU page. In on-demand mode the integrated GPU is treated as the always-on desktop path while the NVIDIA device remains separately detectable.

## Fan telemetry

The native telemetry service reads the G6 KF EC through Linux ec_sys and writes:

/run/g6-control-center/telemetry.json

The verified G6 KF fan/temperature offsets are kept in one place in the service so the GUI never needs privileged EC access.

The current fan backend is read-only. Independent fan control is deliberately disabled while the exact useful control semantics for this EC are being validated.

## Battery

Battery data is read directly from /sys/class/power_supply/BAT*.

Health uses full-charge versus design capacity/energy when the kernel exposes those values. Charge-limit controls are enabled only when a writable threshold sysfs attribute is actually present.

## Privilege model

Only a small allow-listed helper is executed through pkexec for control actions.

The native fan telemetry service runs as root because the EC debugfs interface is normally privileged. It only reads the EC in the current stage and publishes a world-readable, short-lived local snapshot.

## Third-party hardware tools

The application no longer calls gigactl. The native backend owns its telemetry path.

## Roadmap

Validated EC writes, native RGB control, non-blocking control workers, graphs, game profiles and richer packaging are later milestones.
