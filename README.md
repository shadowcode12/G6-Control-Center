# G6 Control Center

A Windows-first, independent control center for the GIGABYTE G6 KF. The active Windows application is built with **C# / WPF on .NET 10**. The earlier PySide6 prototype remains in `app/` as historical work and is not the current Windows application.

> This project is independent and is not affiliated with GIGABYTE or CLEVO. OEM software is studied only for interoperability research; no OEM executable or proprietary implementation is copied into this repository.

## Windows application

### Current milestone: v0.1.2 — reliable startup + read-only telemetry

- WPF application using an MVVM-style structure.
- CPU utilization through Windows `GetSystemTimes`.
- Physical memory through `GlobalMemoryStatusEx`.
- System drive capacity and usage through `DriveInfo`.
- System uptime through `Environment.TickCount64`.
- Startup and unhandled-exception logging to `%LOCALAPPDATA%\G6ControlCenter\Logs\startup.log`.
- Standard WPF `StartupUri` lifecycle with `OnMainWindowClose` shutdown.
- No third-party NuGet packages in the initial Windows application.

### Requirements

- Windows 10/11 x64
- .NET 10 SDK
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

The current Windows application is monitoring-only. It does **not** write to EC/SMBus/ACPI/HID, change fan curves, set CPU power limits, switch GPU modes, or alter battery charge thresholds. It does not load OEM DLLs. Temperature and fan RPM values will be added only after a trustworthy sensor source is validated on this exact laptop. Current telemetry does not require Administrator privileges.

## Repository layout

```text
G6ControlCenter.sln                 # Windows solution
src/G6ControlCenter/                 # C# / WPF Windows app
  Infrastructure/                    # ObservableObject base
  Models/                             # Immutable telemetry models
  Services/                           # Read-only Windows metrics
  ViewModels/                         # Dashboard state and bindings
app/                                  # Earlier PySide6 prototype (preserved)
docs/                                 # Research notes and diagnostic guidance
.github/workflows/windows-build.yml  # Windows CI build
```

## Roadmap

1. Reliable app startup and read-only telemetry.
2. Exact hardware inventory and sensor-source validation.
3. Read-only device capability discovery.
4. Hardware abstraction layer with per-feature capability gates.
5. Carefully scoped controls with bounds, confirmation, rollback and audit logs.
6. Packaging, diagnostics and background resource profiling.

## Development principles

- Prefer documented Windows APIs over undocumented register writes.
- Keep telemetry lightweight and rate-limited.
- Hardware writes remain disabled until device-specific protocols are verified.
- Separate confirmed observations from hypotheses in research notes.
- Preserve the ability to revert every control change.
