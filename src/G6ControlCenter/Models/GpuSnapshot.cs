namespace G6ControlCenter.Models;

/// <summary>
/// Driver-reported NVIDIA GPU telemetry. Null values mean the driver did not provide that field.
/// </summary>
public sealed record GpuSnapshot(
    bool IsAvailable,
    string Name,
    double? TemperatureC,
    double? UtilizationPercent,
    double? PowerWatts,
    double? MemoryUsedMiB,
    double? MemoryTotalMiB,
    double? GraphicsClockMHz,
    double? MemoryClockMHz,
    string DriverVersion,
    string StatusMessage)
{
    public static GpuSnapshot Unavailable(string message) =>
        new(
            IsAvailable: false,
            Name: "NVIDIA GPU unavailable",
            TemperatureC: null,
            UtilizationPercent: null,
            PowerWatts: null,
            MemoryUsedMiB: null,
            MemoryTotalMiB: null,
            GraphicsClockMHz: null,
            MemoryClockMHz: null,
            DriverVersion: "N/A",
            StatusMessage: message);
}
