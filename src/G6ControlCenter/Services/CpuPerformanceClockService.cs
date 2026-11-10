using System.Runtime.Intrinsics.X86;
using System.Runtime.InteropServices;

namespace G6ControlCenter.Services;

/// <summary>
/// Estimates effective CPU frequency from the Windows Processor Performance counter.
/// This is a derived estimate, not a direct per-core hardware clock reading.
/// </summary>
public sealed class CpuPerformanceClockService : IDisposable
{
    private const uint PdhFormatDouble = 0x00000200;
    private const uint PdhStatusValidData = 0x00000000;
    private const uint PdhStatusNewData = 0x00000001;
    private const string CounterPath =
        @"\Processor Information(_Total)\% Processor Performance";

    private readonly IntPtr _query;
    private readonly IntPtr _counter;
    private bool _disposed;

    public int? BaseClockMHz { get; }
    public int? MaximumClockMHz { get; }
    public string StatusMessage { get; private set; } =
        "Waiting for Windows Processor Performance telemetry.";

    public CpuPerformanceClockService()
    {
        (BaseClockMHz, MaximumClockMHz) = ReadNominalFrequencies();

        if (BaseClockMHz is null)
        {
            StatusMessage =
                "CPU frequency estimate unavailable: CPUID leaf 0x16 did not report a nominal clock.";
            return;
        }

        try
        {
            var status = PdhOpenQueryW(IntPtr.Zero, UIntPtr.Zero, out _query);
            if (status != 0)
            {
                StatusMessage = $"PDH query initialization failed (0x{status:X8}).";
                return;
            }

            status = PdhAddEnglishCounterW(
                _query,
                CounterPath,
                UIntPtr.Zero,
                out _counter);

            if (status != 0)
            {
                StatusMessage = $"Processor Performance counter unavailable (0x{status:X8}).";
                return;
            }

            // Prime the query. PDH average/rate counters need a second sample.
            status = PdhCollectQueryData(_query);
            StatusMessage = status == 0
                ? $"Sampling Windows Processor Performance · nominal clock {BaseClockMHz} MHz."
                : $"PDH initial sample failed (0x{status:X8}).";
        }
        catch (DllNotFoundException)
        {
            StatusMessage = "PDH telemetry unavailable: pdh.dll was not found.";
        }
        catch (EntryPointNotFoundException)
        {
            StatusMessage = "PDH telemetry unavailable: required counter API was not found.";
        }
    }

    public double? TryReadEffectiveClockMHz()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);

        if (_query == IntPtr.Zero || _counter == IntPtr.Zero || BaseClockMHz is null)
            return null;

        var status = PdhCollectQueryData(_query);
        if (status != 0)
        {
            StatusMessage = $"PDH sample failed (0x{status:X8}).";
            return null;
        }

        status = PdhGetFormattedCounterValue(
            _counter,
            PdhFormatDouble,
            out _,
            out var value);

        if (status != 0 ||
            value.CStatus is not (PdhStatusValidData or PdhStatusNewData) ||
            !double.IsFinite(value.DoubleValue) ||
            value.DoubleValue <= 0 ||
            value.DoubleValue > 1000)
        {
            StatusMessage = status != 0
                ? $"PDH formatted value unavailable (0x{status:X8})."
                : "Waiting for a valid, non-idle PDH sample.";
            return null;
        }

        var effectiveClockMHz = BaseClockMHz.Value * value.DoubleValue / 100.0;
        if (!double.IsFinite(effectiveClockMHz) ||
            effectiveClockMHz <= 0 ||
            effectiveClockMHz > 10_000)
        {
            StatusMessage = "Windows returned an out-of-range Processor Performance value.";
            return null;
        }

        var maxText = MaximumClockMHz is int max ? $" · CPUID max {max} MHz" : string.Empty;
        StatusMessage =
            $"Estimated from Windows Processor Performance · base {BaseClockMHz} MHz{maxText} · {value.DoubleValue:0.0}%";
        return effectiveClockMHz;
    }

    private static (int? BaseMHz, int? MaxMHz) ReadNominalFrequencies()
    {
        if (!X86Base.IsSupported)
            return (null, null);

        var maximumLeaf = X86Base.CpuId(0, 0).Eax;
        if (maximumLeaf < 0x16)
            return (null, null);

        var frequencies = X86Base.CpuId(0x16, 0);
        var baseMHz = frequencies.Eax > 0 && frequencies.Eax <= 10_000
            ? frequencies.Eax
            : (int?)null;
        var maxMHz = frequencies.Ebx > 0 && frequencies.Ebx <= 20_000
            ? frequencies.Ebx
            : (int?)null;

        return (baseMHz, maxMHz);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        if (_query != IntPtr.Zero)
        {
            try
            {
                PdhCloseQuery(_query);
            }
            catch
            {
                // Best-effort release.
            }
        }
    }

    [StructLayout(LayoutKind.Explicit, Size = 16)]
    private struct PdhFormattedCounterValue
    {
        [FieldOffset(0)]
        public uint CStatus;

        [FieldOffset(8)]
        public double DoubleValue;
    }

    [DllImport("pdh.dll", EntryPoint = "PdhOpenQueryW", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint PdhOpenQueryW(
        IntPtr dataSource,
        UIntPtr userData,
        out IntPtr query);

    [DllImport("pdh.dll", EntryPoint = "PdhAddEnglishCounterW", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint PdhAddEnglishCounterW(
        IntPtr query,
        string fullCounterPath,
        UIntPtr userData,
        out IntPtr counter);

    [DllImport("pdh.dll", EntryPoint = "PdhCollectQueryData", ExactSpelling = true)]
    private static extern uint PdhCollectQueryData(IntPtr query);

    [DllImport("pdh.dll", EntryPoint = "PdhGetFormattedCounterValue", ExactSpelling = true)]
    private static extern uint PdhGetFormattedCounterValue(
        IntPtr counter,
        uint format,
        out uint counterType,
        out PdhFormattedCounterValue value);

    [DllImport("pdh.dll", EntryPoint = "PdhCloseQuery", ExactSpelling = true)]
    private static extern uint PdhCloseQuery(IntPtr query);
}
