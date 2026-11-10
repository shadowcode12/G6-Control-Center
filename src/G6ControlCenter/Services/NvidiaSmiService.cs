using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.ComponentModel;
using G6ControlCenter.Models;

namespace G6ControlCenter.Services;

/// <summary>
/// Reads NVIDIA telemetry through the driver's nvidia-smi utility.
/// This service is read-only and never changes clocks, power limits or GPU modes.
/// </summary>
public sealed class NvidiaSmiService
{
    private static readonly TimeSpan QueryTimeout = TimeSpan.FromSeconds(3);

    private const string QueryArguments =
        "--query-gpu=name,temperature.gpu,utilization.gpu,power.draw," +
        "memory.used,memory.total,clocks.gr,clocks.mem,driver_version " +
        "--format=csv,noheader,nounits";

    public async Task<GpuSnapshot> ReadAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var executable = FindNvidiaSmi();
        if (executable is null)
        {
            return GpuSnapshot.Unavailable(
                "nvidia-smi was not found. Check that the NVIDIA driver is installed and the dGPU is enabled.");
        }

        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = executable,
                Arguments = QueryArguments,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                WorkingDirectory = Environment.SystemDirectory
            }
        };

        try
        {
            if (!process.Start())
                return GpuSnapshot.Unavailable("Could not start nvidia-smi.");
        }
        catch (Exception ex) when (ex is Win32Exception or InvalidOperationException or IOException)
        {
            return GpuSnapshot.Unavailable($"Could not start nvidia-smi: {ex.Message}");
        }

        var standardOutput = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var standardError = process.StandardError.ReadToEndAsync(cancellationToken);

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(QueryTimeout);

        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            TryKill(process);
            return GpuSnapshot.Unavailable("NVIDIA telemetry query timed out.");
        }
        catch (OperationCanceledException)
        {
            TryKill(process);
            throw;
        }

        var output = await standardOutput;
        var error = await standardError;

        if (process.ExitCode != 0)
        {
            var detail = string.IsNullOrWhiteSpace(error)
                ? $"nvidia-smi exited with code {process.ExitCode}."
                : Limit(error.Trim(), 180);

            return GpuSnapshot.Unavailable(detail);
        }

        var line = output
            .Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .FirstOrDefault();

        if (string.IsNullOrWhiteSpace(line))
            return GpuSnapshot.Unavailable("NVIDIA driver returned no GPU telemetry.");

        var fields = line.Split(',').Select(CleanField).ToArray();
        if (fields.Length < 9 || string.IsNullOrWhiteSpace(fields[0]))
            return GpuSnapshot.Unavailable("NVIDIA driver returned an unexpected telemetry format.");

        var driverVersion = IsUnavailable(fields[8]) ? "Unknown" : fields[8];
        var status = $"Online · NVIDIA driver {driverVersion} · refreshed every 3 seconds";

        return new GpuSnapshot(
            IsAvailable: true,
            Name: fields[0],
            TemperatureC: ParseNumber(fields[1]),
            UtilizationPercent: ParseNumber(fields[2]),
            PowerWatts: ParseNumber(fields[3]),
            MemoryUsedMiB: ParseNumber(fields[4]),
            MemoryTotalMiB: ParseNumber(fields[5]),
            GraphicsClockMHz: ParseNumber(fields[6]),
            MemoryClockMHz: ParseNumber(fields[7]),
            DriverVersion: driverVersion,
            StatusMessage: status);
    }

    private static string? FindNvidiaSmi()
    {
        var candidates = new List<string>
        {
            Path.Combine(Environment.SystemDirectory, "nvidia-smi.exe"),
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
        };

        var path = Environment.GetEnvironmentVariable("PATH");
        if (!string.IsNullOrWhiteSpace(path))
        {
            candidates.AddRange(
                path.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries)
                    .Select(directory => Path.Combine(directory.Trim(), "nvidia-smi.exe")));
        }

        return candidates.FirstOrDefault(File.Exists);
    }

    private static string CleanField(string value) =>
        value.Trim().Trim('"');

    private static double? ParseNumber(string value)
    {
        if (IsUnavailable(value))
            return null;

        return double.TryParse(
            value,
            NumberStyles.Float,
            CultureInfo.InvariantCulture,
            out var number)
            ? number
            : null;
    }

    private static bool IsUnavailable(string value) =>
        string.IsNullOrWhiteSpace(value) ||
        value.Equals("N/A", StringComparison.OrdinalIgnoreCase) ||
        value.Equals("[N/A]", StringComparison.OrdinalIgnoreCase) ||
        value.Equals("Not Supported", StringComparison.OrdinalIgnoreCase) ||
        value.Equals("[Not Supported]", StringComparison.OrdinalIgnoreCase);

    private static string Limit(string value, int maxLength) =>
        value.Length <= maxLength ? value : value[..maxLength] + "…";

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);
        }
        catch
        {
            // Best-effort cleanup only.
        }
    }
}
