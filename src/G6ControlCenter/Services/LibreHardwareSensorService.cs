using System.Globalization;
using System.IO;
using System.Security.Principal;
using G6ControlCenter.Models;
using LibreHardwareMonitor.Hardware;

namespace G6ControlCenter.Services;

/// <summary>
/// Read-only sensor discovery through LibreHardwareMonitor.
/// No fan controls, EC writes, clock changes or power-limit changes are performed.
/// </summary>
public sealed class LibreHardwareSensorService : IDisposable
{
    private sealed record SensorObservation(
        string Hardware,
        string Sensor,
        string Type,
        double? Value);

    private readonly object _gate = new();
    private readonly Computer _computer;
    private readonly bool _isOpen;
    private readonly string? _openError;
    private bool _disposed;
    private bool _diagnosticWritten;

    private static readonly string DiagnosticPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "G6ControlCenter",
        "Logs",
        "hardware-sensors.log");

    public LibreHardwareSensorService()
    {
        _computer = new Computer
        {
            IsCpuEnabled = true,
            IsGpuEnabled = true,
            IsMotherboardEnabled = true,
            IsControllerEnabled = true
        };

        try
        {
            _computer.Open();
            _isOpen = true;
        }
        catch (Exception ex)
        {
            _openError = $"{ex.GetType().Name}: {ex.Message}";
        }
    }

    public HardwareSensorSnapshot ReadSnapshot()
    {
        lock (_gate)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);

            if (!_isOpen)
            {
                var errorStatus =
                    $"Hardware sensor access could not initialize: {_openError}. Some sensors may require Administrator access.";
                var reportPath = WriteOpenFailureReport(_openError ?? "Unknown initialization error.");
                return new HardwareSensorSnapshot(
                    null, "Not exposed", null, null, Array.Empty<FanSensorReading>(),
                    errorStatus, reportPath);
            }

            var hardware = EnumerateHardware(_computer.Hardware).ToArray();
            var updateFailures = 0;

            foreach (var device in hardware)
            {
                try
                {
                    device.Update();
                }
                catch
                {
                    updateFailures++;
                }
            }

            var cpuDevices = hardware
                .Where(device => device.HardwareType.ToString().Equals("Cpu", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            var cpuSensors = cpuDevices.SelectMany(device => device.Sensors
                .Select(sensor => new SensorObservation(
                    device.Name,
                    sensor.Name,
                    sensor.SensorType.ToString(),
                    sensor.Value.HasValue && float.IsFinite(sensor.Value.Value)
                        ? (double?)sensor.Value.Value
                        : null)))
                .ToArray();

            var temperatures = cpuSensors
                .Where(sensor =>
                    sensor.Type.Equals("Temperature", StringComparison.OrdinalIgnoreCase) &&
                    sensor.Value is > 0 and < 130)
                .ToArray();

            var preferredTemperature = temperatures.FirstOrDefault(sensor =>
                    sensor.Sensor.Contains("Package", StringComparison.OrdinalIgnoreCase))
                ?? temperatures.FirstOrDefault(sensor =>
                    sensor.Sensor.Contains("Core Max", StringComparison.OrdinalIgnoreCase))
                ?? temperatures.OrderByDescending(sensor => sensor.Value).FirstOrDefault();

            var cpuClocks = cpuSensors
                .Where(sensor =>
                    sensor.Type.Equals("Clock", StringComparison.OrdinalIgnoreCase) &&
                    sensor.Value is > 0 and < 10000 &&
                    sensor.Sensor.Contains("Core", StringComparison.OrdinalIgnoreCase))
                .Select(sensor => sensor.Value!.Value)
                .ToArray();

            var cpuPowerSensors = cpuSensors
                .Where(sensor =>
                    sensor.Type.Equals("Power", StringComparison.OrdinalIgnoreCase) &&
                    sensor.Value is > 0.1 and < 300)
                .ToArray();

            var preferredPower = cpuPowerSensors.FirstOrDefault(sensor =>
                    sensor.Sensor.Contains("Package", StringComparison.OrdinalIgnoreCase))
                ?? cpuPowerSensors.FirstOrDefault();

            var fans = hardware
                .SelectMany(device => device.Sensors
                    .Where(sensor =>
                        sensor.SensorType.ToString().Equals("Fan", StringComparison.OrdinalIgnoreCase) &&
                        sensor.Value.HasValue &&
                        float.IsFinite(sensor.Value.Value) &&
                        sensor.Value.Value >= 0)
                    .Select(sensor => new FanSensorReading(
                        device.Name,
                        sensor.Name,
                        sensor.Value!.Value)))
                .OrderBy(fan => fan.HardwareName, StringComparer.OrdinalIgnoreCase)
                .ThenBy(fan => fan.SensorName, StringComparer.OrdinalIgnoreCase)
                .Take(8)
                .ToArray();

            var diagnosticPath = _diagnosticWritten
                ? DiagnosticPath
                : WriteDiagnosticReport(hardware, cpuDevices, cpuSensors, fans, updateFailures);

            _diagnosticWritten = true;

            var populatedCpuSensors = cpuSensors.Count(sensor => sensor.Value.HasValue);
            var status = $"LibreHardwareMonitor · {hardware.Length} hardware nodes · " +
                         $"{populatedCpuSensors} CPU sensor values · {fans.Length} fan sensors";

            if (updateFailures > 0)
                status += $" · {updateFailures} update failures";
            if (preferredTemperature is null)
                status += " · CPU temperature unavailable";
            if (fans.Length == 0)
                status += " · fan RPM not exposed";

            return new HardwareSensorSnapshot(
                CpuTemperatureC: preferredTemperature?.Value,
                CpuTemperatureSource: preferredTemperature?.Sensor ?? "Not exposed",
                CpuClockMHz: cpuClocks.Length > 0 ? cpuClocks.Average() : null,
                CpuPackagePowerW: preferredPower?.Value,
                Fans: fans,
                StatusMessage: status,
                DiagnosticPath: diagnosticPath);
        }
    }

    private static string WriteOpenFailureReport(string error)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(DiagnosticPath)!);
            File.WriteAllText(
                DiagnosticPath,
                $"G6 Control Center hardware sensor diagnostic{Environment.NewLine}" +
                $"Timestamp: {DateTimeOffset.Now:O}{Environment.NewLine}" +
                $"Elevated: {IsElevated()}{Environment.NewLine}" +
                $"Computer.Open failed: {error}{Environment.NewLine}");
            return DiagnosticPath;
        }
        catch
        {
            return string.Empty;
        }
    }

    private static string WriteDiagnosticReport(
        IReadOnlyList<IHardware> hardware,
        IReadOnlyList<IHardware> cpuDevices,
        IReadOnlyList<SensorObservation> cpuSensors,
        IReadOnlyList<FanSensorReading> fans,
        int updateFailures)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(DiagnosticPath)!);

            var lines = new List<string>
            {
                "G6 Control Center hardware sensor diagnostic",
                $"Timestamp: {DateTimeOffset.Now:O}",
                $"Elevated: {IsElevated()}",
                $"Hardware nodes: {hardware.Count}",
                $"CPU nodes: {cpuDevices.Count}",
                $"CPU sensor entries: {cpuSensors.Count}",
                $"CPU sensor entries with values: {cpuSensors.Count(sensor => sensor.Value.HasValue)}",
                $"Fan sensor entries with values: {fans.Count}",
                $"Hardware update failures: {updateFailures}",
                string.Empty,
                "HARDWARE AND SENSOR INVENTORY"
            };

            foreach (var device in hardware)
            {
                lines.Add($"[{device.HardwareType}] {device.Name}");

                foreach (var sensor in device.Sensors)
                {
                    var value = sensor.Value.HasValue && float.IsFinite(sensor.Value.Value)
                        ? sensor.Value.Value.ToString("0.##", CultureInfo.InvariantCulture)
                        : "N/A";

                    lines.Add($"  - {sensor.SensorType}: {sensor.Name} = {value}");
                }
            }

            File.WriteAllLines(DiagnosticPath, lines);
            return DiagnosticPath;
        }
        catch
        {
            return string.Empty;
        }
    }

    private static bool IsElevated()
    {
        try
        {
            using var identity = WindowsIdentity.GetCurrent();
            return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }
        catch
        {
            return false;
        }
    }

    private static IEnumerable<IHardware> EnumerateHardware(IEnumerable<IHardware> roots)
    {
        foreach (var hardware in roots)
        {
            yield return hardware;

            foreach (var child in EnumerateHardware(hardware.SubHardware))
                yield return child;
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed) return;
            _disposed = true;

            if (_isOpen)
            {
                try
                {
                    _computer.Close();
                }
                catch
                {
                    // Best-effort release of sensor handles.
                }
            }
        }
    }
}
