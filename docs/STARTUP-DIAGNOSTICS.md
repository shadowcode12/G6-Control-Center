# Startup diagnostics

The Windows app writes startup, shutdown and unhandled exception messages to:

`%LOCALAPPDATA%\G6ControlCenter\Logs\startup.log`

The app uses WPF's standard `StartupUri="MainWindow.xaml"` lifecycle. If the process starts and exits immediately, check the log first. If no log is created, run the executable directly and collect the Windows Application event log entry for `G6ControlCenter.exe`.

Commands from the repository root:

```powershell
dotnet clean .\G6ControlCenter.sln
dotnet build .\G6ControlCenter.sln -c Debug -v minimal
dotnet run --no-build --project .\src\G6ControlCenter\G6ControlCenter.csproj
```

Direct executable:

```powershell
.\src\G6ControlCenter\bin\Debug\net10.0-windows\G6ControlCenter.exe
```
