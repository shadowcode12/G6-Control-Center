namespace G6ControlCenter.Models;

/// <summary>
/// Read-only snapshot of Windows metrics that are available without vendor-specific drivers.
/// Temperatures, fan RPM and EC values are deliberately not fabricated here.
/// </summary>
public sealed record SystemSnapshot(
    double CpuUsagePercent,
    double MemoryUsagePercent,
    double MemoryUsedGiB,
    double MemoryTotalGiB,
    double SystemDriveUsedPercent,
    double SystemDriveUsedGiB,
    double SystemDriveTotalGiB,
    string SystemDriveName,
    TimeSpan Uptime,
    DateTimeOffset SampledAt);
