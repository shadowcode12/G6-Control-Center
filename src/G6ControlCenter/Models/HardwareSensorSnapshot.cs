namespace G6ControlCenter.Models;

public sealed record FanSensorReading(
    string HardwareName,
    string SensorName,
    double Rpm);

/// <summary>
/// Read-only temperature, clock, power and fan observations from supported hardware sensors.
/// Missing values are represented as null; no values are estimated.
/// </summary>
public sealed record HardwareSensorSnapshot(
    double? CpuTemperatureC,
    string CpuTemperatureSource,
    double? CpuClockMHz,
    double? CpuPackagePowerW,
    IReadOnlyList<FanSensorReading> Fans,
    string StatusMessage)
{
    public static HardwareSensorSnapshot Unavailable(string message) =>
        new(null, "Not exposed", null, null, Array.Empty<FanSensorReading>(), message);
}
