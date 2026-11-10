# G6 Control Center

A Windows-first, independent control center for the GIGABYTE G6 KF. The active Windows application is built with **C# / WPF on .NET 10**. The earlier PySide6 prototype remains in `app/` as historical work and is not the current Windows application.

> This project is independent and is not affiliated with GIGABYTE or CLEVO. OEM software is studied only for interoperability research; no OEM executable or proprietary implementation is copied into this repository.

## Windows application

### Current milestone: v0.3.1 — CPU/GPU telemetry and sensor diagnostics

- WPF application using an MVVM-style structure.
- CPU utilization through Windows `GetSystemTimes`.
- Physical memory through `GlobalMemoryStatusEx`.
- System drive capacity and usage through `DriveInfo`.
- System uptime through `Environment.TickCount64`.
- NVIDIA GPU name, utilization, temperature, power draw, VRAM usage, graphics clock, memory clock and driver version through `nvidia-smi`.
- CPU temperature, reported core clock, CPU package power and fan RPM discovery through `LibreHardwareMonitorLib` 0.9.6.
- A one-time hardware inventory is written to `%LOCALAPPDATA%\\G6ControlCenter\\Logs\\hardware-sensors.log`, including the detected hardware nodes, sensor names, types, values and whether the process was elevated.
- Zero/invalid CPU package-power placeholders are shown as N/A rather than as a real 0.0 W reading.
- Hardware sensor polling runs on a background task every 5 seconds; NVIDIA polling runs every 3 seconds.
- Missing or inaccessible sensors are displayed as N/A/not exposed. No temperature or fan values are estimated.
- Startup and unhandled-exception logging to `%LOCALAPPDATA%\G6ControlCenter\Logs\startup.log`.

### Requirements

- Windows 10/11 x64
- .NET 10 SDK
- NVIDIA driver and `nvidia-smi.exe` for NVIDIA telemetry
- Internet access on first restore to download NuGet packages
- Visual Studio with the .NET desktop development workload (optional; VS Code + SDK is sufficient)

### Build and run (PowerShell)

Run these commands from the repository root:

```powershell
dotnet restore .\G6ControlCenter.sln
dotnet build .\G6ControlCenter.sln -c Debug
dotnet run --no-build --project .\src\G6ControlCenter\G6ControlCenter.csproj
```

### Sensor access and permissions

The hardware sensor library supports Intel CPUs, NVIDIA/AMD/Intel GPUs, motherboards and controllers. Actual sensor availability depends on the laptop's embedded controller, motherboard support and driver access. Some sensors require Administrator privileges. The application does not automatically elevate itself; first test it normally. If the library reports that sensor access is denied, an Administrator-only diagnostic run can be considered separately.

### Diagnostics

If the application exits without showing a window, inspect:

```text
%LOCALAPPDATA%\G6ControlCenter\Logs\startup.log
```

The hardware sensor panel also displays the sensor library's current availability status. The first sensor scan writes a complete inventory to `%LOCALAPPDATA%\\G6ControlCenter\\Logs\\hardware-sensors.log`; this report helps distinguish a missing sensor from a permission or hardware-provider issue.

## Safety boundaries

The current application is monitoring-only. It does **not** write to EC/SMBus/ACPI/HID, change fan curves, set CPU power limits, switch GPU modes, or alter battery charge thresholds. It does not load OEM DLLs. LibreHardwareMonitor is used only for sensor discovery and read-only values. Some sensor providers may require elevated access; the application does not request Administrator privileges by default. Missing readings remain unavailable instead of being fabricated.

## Repository layout

```text
G6ControlCenter.sln
src/G6ControlCenter/
  Infrastructure/
  Models/
  Services/
  ViewModels/
app/                                  # Earlier PySide6 prototype (preserved)
docs/
.github/workflows/windows-build.yml
```

## Roadmap

1. Reliable app startup and Windows read-only telemetry.
2. CPU and NVIDIA GPU telemetry.
3. Validate CPU temperature, CPU clock, package power and fan RPM sensor sources on the exact G6 KF.
4. Exact hardware inventory and read-only device capability discovery.
5. Hardware abstraction layer with per-feature capability gates.
6. Carefully scoped controls with bounds, confirmation, rollback and audit logs.
7. Packaging, diagnostics and background resource profiling.

## Development principles

- Prefer documented Windows APIs and read-only sensor interfaces over undocumented register writes.
- Keep telemetry lightweight and rate-limited.
- Hardware writes remain disabled until device-specific protocols are verified.
- Display unavailable sensor readings as unavailable; never invent or silently substitute values.
- Separate confirmed observations from hypotheses in research notes.
- Preserve the ability to revert every control change.

## Third-party notices

- LibreHardwareMonitorLib is distributed under the Mozilla Public License 2.0. See [the upstream project](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) and [LICENSE](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/blob/master/LICENSE).
