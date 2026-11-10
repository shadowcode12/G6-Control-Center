using System.Globalization;
using System.Windows.Threading;
using G6ControlCenter.Infrastructure;
using G6ControlCenter.Models;
using G6ControlCenter.Services;

namespace G6ControlCenter.ViewModels;

public sealed class MainViewModel : ObservableObject, IDisposable
{
    private readonly SystemMetricsService _metrics = new();
    private readonly NvidiaSmiService _nvidia = new();
    private readonly Dispatcher _dispatcher = Dispatcher.CurrentDispatcher;
    private readonly DispatcherTimer _timer;
    private CancellationTokenSource? _gpuPollingCts;
    private bool _isRunning;
    private string _status = "Ready · read-only monitoring";
    private string _lastUpdated = "Waiting for first sample…";
    private string _cpuValue = "—";
    private string _memoryValue = "—";
    private string _memoryDetail = "—";
    private string _driveValue = "—";
    private string _driveDetail = "—";
    private string _uptimeValue = "—";
    private double _cpuUsage;
    private double _memoryUsage;
    private double _driveUsage;

    private string _gpuName = "Detecting NVIDIA GPU…";
    private string _gpuStatus = "Waiting for NVIDIA driver telemetry…";
    private string _gpuUsageValue = "—";
    private string _gpuTemperatureValue = "—";
    private string _gpuMemoryValue = "—";
    private string _gpuPowerValue = "—";
    private string _gpuUsageDetail = "GPU utilization";
    private string _gpuTemperatureDetail = "Driver-reported GPU core temperature";
    private string _gpuMemoryDetail = "Dedicated video memory";
    private string _gpuPowerDetail = "Driver-reported board power";
    private double _gpuUsage;
    private double _gpuMemoryUsage;

    public MainViewModel()
    {
        _timer = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromSeconds(1)
        };
        _timer.Tick += (_, _) => Refresh();
    }

    public string Status { get => _status; private set => SetProperty(ref _status, value); }
    public string LastUpdated { get => _lastUpdated; private set => SetProperty(ref _lastUpdated, value); }
    public string CpuValue { get => _cpuValue; private set => SetProperty(ref _cpuValue, value); }
    public string MemoryValue { get => _memoryValue; private set => SetProperty(ref _memoryValue, value); }
    public string MemoryDetail { get => _memoryDetail; private set => SetProperty(ref _memoryDetail, value); }
    public string DriveValue { get => _driveValue; private set => SetProperty(ref _driveValue, value); }
    public string DriveDetail { get => _driveDetail; private set => SetProperty(ref _driveDetail, value); }
    public string UptimeValue { get => _uptimeValue; private set => SetProperty(ref _uptimeValue, value); }
    public double CpuUsage { get => _cpuUsage; private set => SetProperty(ref _cpuUsage, value); }
    public double MemoryUsage { get => _memoryUsage; private set => SetProperty(ref _memoryUsage, value); }
    public double DriveUsage { get => _driveUsage; private set => SetProperty(ref _driveUsage, value); }

    public string GpuName { get => _gpuName; private set => SetProperty(ref _gpuName, value); }
    public string GpuStatus { get => _gpuStatus; private set => SetProperty(ref _gpuStatus, value); }
    public string GpuUsageValue { get => _gpuUsageValue; private set => SetProperty(ref _gpuUsageValue, value); }
    public string GpuTemperatureValue { get => _gpuTemperatureValue; private set => SetProperty(ref _gpuTemperatureValue, value); }
    public string GpuMemoryValue { get => _gpuMemoryValue; private set => SetProperty(ref _gpuMemoryValue, value); }
    public string GpuPowerValue { get => _gpuPowerValue; private set => SetProperty(ref _gpuPowerValue, value); }
    public string GpuUsageDetail { get => _gpuUsageDetail; private set => SetProperty(ref _gpuUsageDetail, value); }
    public string GpuTemperatureDetail { get => _gpuTemperatureDetail; private set => SetProperty(ref _gpuTemperatureDetail, value); }
    public string GpuMemoryDetail { get => _gpuMemoryDetail; private set => SetProperty(ref _gpuMemoryDetail, value); }
    public string GpuPowerDetail { get => _gpuPowerDetail; private set => SetProperty(ref _gpuPowerDetail, value); }
    public double GpuUsage { get => _gpuUsage; private set => SetProperty(ref _gpuUsage, value); }
    public double GpuMemoryUsage { get => _gpuMemoryUsage; private set => SetProperty(ref _gpuMemoryUsage, value); }

    public void Start()
    {
        if (_isRunning) return;

        _isRunning = true;
        Refresh();
        _timer.Start();

        _gpuPollingCts = new CancellationTokenSource();
        _ = PollGpuAsync(_gpuPollingCts.Token);
    }

    public void Stop()
    {
        _timer.Stop();
        _isRunning = false;
        _gpuPollingCts?.Cancel();
    }

    private void Refresh()
    {
        try
        {
            SystemSnapshot snapshot = _metrics.ReadSnapshot();
            CpuUsage = snapshot.CpuUsagePercent;
            CpuValue = $"{snapshot.CpuUsagePercent:0}%";
            MemoryUsage = snapshot.MemoryUsagePercent;
            MemoryValue = $"{snapshot.MemoryUsagePercent:0}%";
            MemoryDetail = $"{snapshot.MemoryUsedGiB:0.0} GB used of {snapshot.MemoryTotalGiB:0.0} GB";
            DriveUsage = snapshot.SystemDriveUsedPercent;
            DriveValue = $"{snapshot.SystemDriveUsedPercent:0}%";
            DriveDetail = $"{snapshot.SystemDriveUsedGiB:0.0} GB used of {snapshot.SystemDriveTotalGiB:0.0} GB · {snapshot.SystemDriveName}";
            UptimeValue = FormatUptime(snapshot.Uptime);
            LastUpdated = $"Updated {snapshot.SampledAt:HH:mm:ss}";
            Status = "Online · read-only monitoring";
        }
        catch (Exception ex)
        {
            Status = "Telemetry error · see diagnostics";
            LastUpdated = ex.GetType().Name + ": " + ex.Message;
        }
    }

    private async Task PollGpuAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            GpuSnapshot snapshot;

            try
            {
                snapshot = await _nvidia.ReadAsync(cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception ex)
            {
                snapshot = GpuSnapshot.Unavailable($"GPU telemetry error: {ex.Message}");
            }

            if (cancellationToken.IsCancellationRequested)
                return;

            await _dispatcher.InvokeAsync(() => ApplyGpuSnapshot(snapshot));

            try
            {
                await Task.Delay(TimeSpan.FromSeconds(3), cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
        }
    }

    private void ApplyGpuSnapshot(GpuSnapshot snapshot)
    {
        GpuStatus = snapshot.StatusMessage;

        if (!snapshot.IsAvailable)
        {
            GpuName = snapshot.Name;
            GpuUsageValue = "N/A";
            GpuTemperatureValue = "N/A";
            GpuMemoryValue = "N/A";
            GpuPowerValue = "N/A";
            GpuUsage = 0;
            GpuMemoryUsage = 0;
            GpuUsageDetail = "NVIDIA driver telemetry is unavailable";
            GpuTemperatureDetail = "No temperature reading received";
            GpuMemoryDetail = "No dedicated VRAM reading received";
            GpuPowerDetail = "No power reading received";
            return;
        }

        GpuName = snapshot.Name;
        GpuUsage = snapshot.UtilizationPercent ?? 0;
        GpuUsageValue = FormatMetric(snapshot.UtilizationPercent, "0", "%");
        GpuTemperatureValue = FormatMetric(snapshot.TemperatureC, "0", "°C");
        GpuPowerValue = FormatMetric(snapshot.PowerWatts, "0.0", " W");
        GpuUsageDetail = snapshot.Name;
        GpuTemperatureDetail = "Driver-reported GPU core temperature";

        if (snapshot.MemoryUsedMiB is double usedMiB &&
            snapshot.MemoryTotalMiB is double totalMiB &&
            totalMiB > 0)
        {
            GpuMemoryUsage = Math.Clamp(usedMiB * 100 / totalMiB, 0, 100);
            GpuMemoryValue = $"{usedMiB / 1024:0.0} / {totalMiB / 1024:0.0} GiB";
            GpuMemoryDetail = $"{GpuMemoryUsage:0}% of dedicated VRAM in use";
        }
        else
        {
            GpuMemoryUsage = 0;
            GpuMemoryValue = "N/A";
            GpuMemoryDetail = "Dedicated VRAM usage not reported";
        }

        var clocks = $"Core {FormatMetric(snapshot.GraphicsClockMHz, "0", " MHz")} · Memory {FormatMetric(snapshot.MemoryClockMHz, "0", " MHz")}";
        GpuPowerDetail = $"{clocks} · Driver {snapshot.DriverVersion}";
    }

    private static string FormatMetric(double? value, string format, string suffix) =>
        value is double number
            ? number.ToString(format, CultureInfo.InvariantCulture) + suffix
            : "N/A";

    private static string FormatUptime(TimeSpan uptime)
    {
        var days = (int)uptime.TotalDays;
        return days > 0
            ? $"{days}d {uptime.Hours:00}h {uptime.Minutes:00}m"
            : $"{uptime.Hours:00}h {uptime.Minutes:00}m {uptime.Seconds:00}s";
    }

    public void Dispose()
    {
        Stop();
        _gpuPollingCts?.Dispose();
        _gpuPollingCts = null;
    }
}
