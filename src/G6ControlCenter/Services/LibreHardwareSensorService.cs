using G6ControlCenter.Models;
using LibreHardwareMonitor.Hardware;

namespace G6ControlCenter.Services;

/// <summary>
/// Read-only sensor discovery through LibreHardwareMonitor.
/// No fan controls, EC writes, clock changes or power-limit changes are performed.
/// </summary>
public sealed class LibreHardwareSensorService : IDisposable
{
    private readonly object _gate = new();
    private readonly Computer _computer;
    private readonly bool _isOpen;
    private readonly string? _openError;
    private bool _disposed;

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
                return HardwareSensorSnapshot.Unavailable(
                    $"Hardware sensor access could not initialize: {_openError}. Some sensors may require running the app as Administrator.");
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
                .Where(sensor => sensor.Value.HasValue)
                .Select(sensor => new
                {
                    Hardware = device.Name,
                    Sensor = sensor.Name,
                    Type = sensor.SensorType.ToString(),
                    Value = (double)sensor.Value!.Value
                }))
                .ToArray();

            var temperatures = cpuSensors
                .Where(sensor => sensor.Type.Equals("Temperature", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            var preferredTemperature = temperatures.FirstOrDefault(sensor =>
                    sensor.Sensor.Contains("Package", StringComparison.OrdinalIgnoreCase))
                ?? temperatures.FirstOrDefault(sensor =>
                    sensor.Sensor.Contains("Core Max", StringComparison.OrdinalIgnoreCase))
                ?? temperatures.OrderByDescending(sensor => sensor.Value).FirstOrDefault();

            var cpuClocks = cpuSensors
                .Where(sensor =>
                    sensor.Type.Equals("Clock", StringComparison.OrdinalIgnoreCase) &&
                    sensor.Value > 0 &&
                    sensor.Sensor.Contains("Core", StringComparison.OrdinalIgnoreCase))
                .Select(sensor => sensor.Value)
                .ToArray();

            var cpuPowerSensors = cpuSensors
                .Where(sensor => sensor.Type.Equals("Power", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            var preferredPower = cpuPowerSensors.FirstOrDefault(sensor =>
                    sensor.Sensor.Contains("Package", StringComparison.OrdinalIgnoreCase))
                ?? cpuPowerSensors.FirstOrDefault();

            var fans = hardware
                .SelectMany(device => device.Sensors
                    .Where(sensor =>
                        sensor.SensorType.ToString().Equals("Fan", StringComparison.OrdinalIgnoreCase) &&
                        sensor.Value.HasValue &&
                        sensor.Value.Value > 0)
                    .Select(sensor => new FanSensorReading(
                        device.Name,
                        sensor.Name,
                        sensor.Value!.Value)))
                .OrderBy(fan => fan.HardwareName, StringComparer.OrdinalIgnoreCase)
                .ThenBy(fan => fan.SensorName, StringComparer.OrdinalIgnoreCase)
                .Take(6)
                .ToArray();

            var hasCpuData = preferredTemperature is not null ||
                             cpuClocks.Length > 0 ||
                             preferredPower is not null;

            string status;
            if (!hasCpuData && fans.Length == 0)
            {
                status = updateFailures > 0
                    ? "Sensor library initialized, but hardware readings are unavailable. Some sensors may require Administrator access."
                    : "No CPU temperature or fan sensors were exposed by this laptop's current hardware interfaces.";
            }
            else
            {
                var parts = new List<string> { "LibreHardwareMonitor · read-only" };
                if (updateFailures > 0)
                    parts.Add($"{updateFailures} sensor provider(s) unavailable");
                if (fans.Length == 0)
                    parts.Add("fan RPM not exposed");
                status = string.Join(" · ", parts);
            }

            return new HardwareSensorSnapshot(
                CpuTemperatureC: preferredTemperature?.Value,
                CpuTemperatureSource: preferredTemperature?.Sensor ?? "Not exposed",
                CpuClockMHz: cpuClocks.Length > 0 ? cpuClocks.Average() : null,
                CpuPackagePowerW: preferredPower?.Value,
                Fans: fans,
                StatusMessage: status);
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
