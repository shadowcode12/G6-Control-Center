using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using G6ControlCenter.Models;

namespace G6ControlCenter.Services;

/// <summary>
/// Lightweight Windows telemetry using documented OS APIs. No polling of EC/SMBus,
/// no driver writes, and no vendor DLL loading.
/// </summary>
public sealed class SystemMetricsService
{
    private ulong? _previousIdle;
    private ulong? _previousKernel;
    private ulong? _previousUser;

    public SystemSnapshot ReadSnapshot()
    {
        var cpu = ReadCpuUsage();
        var memory = ReadMemory();
        var drive = ReadSystemDrive();

        return new SystemSnapshot(
            CpuUsagePercent: cpu,
            MemoryUsagePercent: memory.UsagePercent,
            MemoryUsedGiB: memory.UsedGiB,
            MemoryTotalGiB: memory.TotalGiB,
            SystemDriveUsedPercent: drive.UsedPercent,
            SystemDriveUsedGiB: drive.UsedGiB,
            SystemDriveTotalGiB: drive.TotalGiB,
            SystemDriveName: drive.Name,
            Uptime: TimeSpan.FromMilliseconds(Environment.TickCount64),
            SampledAt: DateTimeOffset.Now);
    }

    private double ReadCpuUsage()
    {
        if (!GetSystemTimes(out var idleTime, out var kernelTime, out var userTime))
            throw new Win32Exception(Marshal.GetLastWin32Error(), "GetSystemTimes failed.");

        var idle = ToUInt64(idleTime);
        var kernel = ToUInt64(kernelTime);
        var user = ToUInt64(userTime);

        if (_previousIdle is null || _previousKernel is null || _previousUser is null)
        {
            _previousIdle = idle;
            _previousKernel = kernel;
            _previousUser = user;
            return 0;
        }

        var idleDelta = idle - _previousIdle.Value;
        var kernelDelta = kernel - _previousKernel.Value;
        var userDelta = user - _previousUser.Value;
        var total = kernelDelta + userDelta;

        _previousIdle = idle;
        _previousKernel = kernel;
        _previousUser = user;

        if (total == 0) return 0;
        var busy = total > idleDelta ? total - idleDelta : 0;
        return Math.Clamp(busy * 100d / total, 0d, 100d);
    }

    private static (double UsagePercent, double UsedGiB, double TotalGiB) ReadMemory()
    {
        var status = new MemoryStatusEx { Length = (uint)Marshal.SizeOf<MemoryStatusEx>() };
        if (!GlobalMemoryStatusEx(ref status))
            throw new Win32Exception(Marshal.GetLastWin32Error(), "GlobalMemoryStatusEx failed.");

        const double bytesPerGiB = 1024d * 1024d * 1024d;
        var total = status.TotalPhysical;
        var available = status.AvailablePhysical;
        var used = total >= available ? total - available : 0;
        var percent = total == 0 ? 0 : used * 100d / total;

        return (Math.Clamp(percent, 0, 100), used / bytesPerGiB, total / bytesPerGiB);
    }

    private static (double UsedPercent, double UsedGiB, double TotalGiB, string Name) ReadSystemDrive()
    {
        var root = Path.GetPathRoot(Environment.SystemDirectory);
        if (string.IsNullOrWhiteSpace(root))
            return (0, 0, 0, "System drive unavailable");

        var drive = new DriveInfo(root);
        if (!drive.IsReady || drive.TotalSize <= 0)
            return (0, 0, 0, root);

        const double bytesPerGiB = 1024d * 1024d * 1024d;
        var used = Math.Max(0, drive.TotalSize - drive.AvailableFreeSpace);
        var percent = used * 100d / drive.TotalSize;
        return (Math.Clamp(percent, 0, 100), used / bytesPerGiB, drive.TotalSize / bytesPerGiB, drive.Name);
    }

    private static ulong ToUInt64(FileTime value) =>
        ((ulong)value.High << 32) | value.Low;

    [StructLayout(LayoutKind.Sequential)]
    private struct FileTime
    {
        public uint Low;
        public uint High;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct MemoryStatusEx
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhysical;
        public ulong AvailablePhysical;
        public ulong TotalPageFile;
        public ulong AvailablePageFile;
        public ulong TotalVirtual;
        public ulong AvailableVirtual;
        public ulong AvailableExtendedVirtual;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetSystemTimes(out FileTime idleTime, out FileTime kernelTime, out FileTime userTime);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatusEx buffer);
}
