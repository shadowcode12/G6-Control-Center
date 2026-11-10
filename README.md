# G6 Control Center

A Windows-first, independent control center for the GIGABYTE G6 KF. The active Windows application is built with **C# / WPF on .NET 10**. The earlier PySide6 prototype remains in `app/` as historical work and is not the current Windows application.

> This project is independent and is not affiliated with GIGABYTE or CLEVO. OEM software is studied only for interoperability research; no OEM executable or proprietary implementation is copied into this repository.

## Windows application

### Current milestone: v0.2.0 — read-only CPU, memory, storage and NVIDIA telemetry

- WPF application using an MVVM-style structure.
- CPU utilization through Windows `GetSystemTimes`.
- Physical memory through `GlobalMemoryStatusEx`.
- System drive capacity and usage through `DriveInfo`.
- System uptime through `Environment.TickCount64`.
- NVIDIA GPU name, utilization, temperature, power draw, VRAM usage, graphics clock, memory clock and driver version through `nvidia-smi`.
- NVIDIA polling runs asynchronously every 3 seconds with a 3-second process timeout; it does not block the UI thread.
- Startup and unhandled-exception logging to `%LOCALAPPDATA%\G6ControlCenter\Logs\startup.log`.
- No third-party NuGet packages in the initial Windows application.

### Requirements

- Windows 10/11 x64
- .NET 10 SDK
- NVIDIA driver and `nvidia-smi.exe` for NVIDIA telemetry (GPU metrics show N/A when the NVIDIA utility/device is unavailable)
- Visual Studio with the .NET desktop development workload (optional; VS Code + SDK is sufficient)

### Build and run (PowerShell)

Run these commands from the repository root:

```powershell
dotnet --list-sdks
dotnet restore .\G6ControlCenter.sln
dotnet build .\G6ControlCenter.sln -c Debug
dotnet run --no-build --project .\src\G6ControlCenter\G6ControlCenter.csproj
```

To launch the built Windows executable directly:

```powershell
.\src\G6ControlCenter\bin\Debug\net10.0-windows\G6ControlCenter.exe
```

### Diagnostics

If the application exits without showing a window, inspect:

```text
%LOCALAPPDATA%\G6ControlCenter\Logs\startup.log
```

Share the log together with the output of `dotnet run --no-build --project .\src\G6ControlCenter\G6ControlCenter.csproj` when reporting a startup problem.

## Safety boundaries

The current Windows application is monitoring-only. It does **not** write to EC/SMBus/ACPI/HID, change fan curves, set CPU power limits, switch GPU modes, or alter battery charge thresholds. It does not load OEM DLLs. CPU temperature and fan RPM will be added only after a trustworthy sensor source is validated on this exact laptop. NVIDIA telemetry is read-only and uses the vendor's `nvidia-smi` query interface. Current telemetry does not require Administrator privileges.

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
3. Exact hardware inventory and sensor-source validation.
4. Read-only device capability discovery.
5. Hardware abstraction layer with per-feature capability gates.
6. Carefully scoped controls with bounds, confirmation, rollback and audit logs.
7. Packaging, diagnostics and background resource profiling.

## Development principles

- Prefer documented Windows APIs and NVIDIA's read-only query interface over undocumented register writes.
- Keep telemetry lightweight and rate-limited.
- Hardware writes remain disabled until device-specific protocols are verified.
- Display unavailable sensor readings as unavailable; never invent or silently substitute values.
- Separate confirmed observations from hypotheses in research notes.
- Preserve the ability to revert every control change.
