# Architecture

G6 Control Center is a PySide6 GUI with isolated Linux hardware adapters.

## Hardware layers

`app/ui` contains presentation only.

`app/backend` talks to Linux sysfs/DRM, NVIDIA, the native EC telemetry snapshot and standard power-management interfaces.

`app/services` contains fixed-action privileged operations and the native root-owned telemetry service.

## GPU

The graphics layer combines NVIDIA `nvidia-smi` telemetry and Intel DRM/sysfs telemetry. PRIME mode selects the preferred GPU for the live GPU page. NVIDIA default power/TGP is informational only; user power-limit, voltage, overclocking and undervolting controls are intentionally absent.

## Fans

The native telemetry service reads the verified G6 KF EC registers for CPU/GPU temperature, fan duty and fan tach period, then publishes `/run/g6-control-center/telemetry.json`. The GUI polls that file once per second. Manual fan control is not exposed because this stage is telemetry-first and avoids risky EC writes.

## Battery

Battery telemetry is read from `/sys/class/power_supply/BAT*`. When the active driver exposes the standard start/end threshold files, the UI provides Full Charge, Locked at 80% and Custom modes. Linux defines `charge_type=Custom` as the charging mode that uses `charge_control_*` threshold properties. Clevo-family FlexiCharger support on Linux is dependent on a compatible `clevo_acpi` driver. citeturn592304search0turn318739search5

## CPU

CPU controls are limited to system performance profiles and a three-level Energy Performance Preference UI (Low / Mid / High). CPU RAPL power-limit controls, Turbo toggles and voltage controls are intentionally removed from the application surface.

## Privilege model

Only fixed, allow-listed operations use the root-owned PolicyKit helper. The native EC telemetry service runs as root and is read-only in the current stage.

## Roadmap

Hardware-validated EC control, native RGB and richer monitoring are separate milestones. The next hardware milestone is validation, not adding more power/voltage controls.
