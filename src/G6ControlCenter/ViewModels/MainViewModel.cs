using System.Windows.Threading;
using G6ControlCenter.Infrastructure;
using G6ControlCenter.Models;
using G6ControlCenter.Services;

namespace G6ControlCenter.ViewModels;

public sealed class MainViewModel : ObservableObject, IDisposable
{
    private readonly SystemMetricsService _metrics = new();
    private readonly DispatcherTimer _timer;
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

    public void Start()
    {
        if (_isRunning) return;
        _isRunning = true;
        Refresh();
        _timer.Start();
    }

    public void Stop()
    {
        _timer.Stop();
        _isRunning = false;
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

    private static string FormatUptime(TimeSpan uptime)
    {
        var days = (int)uptime.TotalDays;
        return days > 0
            ? $"{days}d {uptime.Hours:00}h {uptime.Minutes:00}m"
            : $"{uptime.Hours:00}h {uptime.Minutes:00}m {uptime.Seconds:00}s";
    }

    public void Dispose() => Stop();
}
