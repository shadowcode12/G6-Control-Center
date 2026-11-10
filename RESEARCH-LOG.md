# OEM and hardware-sensor research log

## Scope

Understand the installed GIGABYTE/CLEVO application architecture on the owner's G6 KF to inform an independent implementation. Do not copy OEM implementation code, redistribute OEM binaries, patch installed executables, or issue unknown hardware writes.

## Observed evidence

- The visible system interface includes System, FlexiCharger, LED Keyboard and Flexikey modules.
- The installed `CLEVOCO.FnhotkeysandOSD` package is x64 and contains a `FnKey\\CC40\\CC40.exe` application.
- The inspected `CC40.exe` is a PE32+ x64 executable with CLR metadata; its package contains WPF-related assemblies, Actipro WPF assemblies and GalaSoft MVVM Light assemblies.
- The package contains multiple native libraries and helper executables, including names associated with DCHU, HID, NVIDIA, keyboard LED and Intel tuning functionality.
- `DCHUService.exe` is registered as the Control Center Hotkey Service. `HKClipSvc.exe` is also present in the ControlCenter driver folder.
- The owner's WMI diagnostic returned no `MSAcpi_ThermalZoneTemperature` instances and no `Win32_Fan` instances. It identified the processor as Intel Core i7-13620H; `CurrentClockSpeed` and `MaxClockSpeed` both returned 2400 MHz, but this WMI snapshot is not treated as live per-core frequency telemetry.
- The G6 Control Center v0.3.0 screenshot showed NVIDIA telemetry working, while LibreHardwareMonitor did not expose CPU temperature, CPU core clocks or fan RPM. CPU package power appeared as 0.0 W; v0.3.1 filters non-positive package-power values as unavailable.

## Sensor-source evaluation

- LibreHardwareMonitor's official project documents support for Intel/AMD CPUs, NVIDIA/AMD/Intel GPUs, motherboards and network/storage devices, and provides a .NET 10-compatible library.
- Its documentation states that some sensors require Administrator privileges and hardware readout methods vary by manufacturer.
- G6 Control Center integrates LibreHardwareMonitorLib 0.9.6 for read-only discovery only. It does not automatically elevate itself.
- Version 0.3.1 writes a one-time hardware/sensor inventory to `%LOCALAPPDATA%\\G6ControlCenter\\Logs\\hardware-sensors.log`, recording the process elevation state and sensor names/types/values.
- A supported sensor library does not guarantee that this exact G6 KF exposes CPU temperature or fan RPM through the library. Results must be validated on the laptop.

## Important limitations

- A bundled DLL does not prove that every feature is active on this laptop or called by CC40 at runtime.
- Function names and imports are leads, not a complete hardware protocol specification.
- Fan control, EC writes, power limits, GPU switching and battery thresholds remain unimplemented until model-specific capabilities and safe bounds are established.
- Do not run unverified IOCTLs or write arbitrary EC/ACPI values.
- Do not treat a missing WMI or third-party sensor as proof that the hardware has no sensor; it may simply not be exposed through that software provider.

## Next research tasks

1. Inspect the v0.3.1 hardware inventory generated on the G6 KF.
2. Compare sensor availability in a one-time elevated diagnostic run; do not set permanent elevation.
3. Compare temperatures with an independent trusted sensor application under idle and controlled load.
4. Determine whether the original vendor service exposes read-only CPU and fan telemetry.
5. Determine which features can be implemented using documented Windows APIs and which require a signed vendor driver or firmware support.
