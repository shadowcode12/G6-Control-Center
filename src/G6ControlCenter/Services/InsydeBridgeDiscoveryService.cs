using System.Runtime.InteropServices;

namespace G6ControlCenter.Services;

/// <summary>
/// Enumerates the published Insyde CLV0001 device interface using Windows Configuration Manager.
/// It does not open the device or send IOCTL, ACPI or EC requests.
/// </summary>
public sealed class InsydeBridgeDiscoveryService
{
    private static readonly Guid InterfaceClassGuid = new("86994c74-ad43-4812-b7e7-0c420b5c5fd7");
    private const uint CmGetDeviceInterfaceListPresent = 0;

    public InsydeBridgeSnapshot Read()
    {
        try
        {
            var guid = InterfaceClassGuid;
            var status = CM_Get_Device_Interface_List_SizeW(out var requiredChars, ref guid, null, CmGetDeviceInterfaceListPresent);
            if (status != 0)
                return InsydeBridgeSnapshot.Unavailable($"Configuration Manager size query failed (CONFIGRET 0x{status:X8}).");
            if (requiredChars <= 1)
                return new InsydeBridgeSnapshot(false, 0, "CLV0001 interface is not currently published.");
            if (requiredChars > 32768)
                return InsydeBridgeSnapshot.Unavailable("Windows returned an unexpectedly large interface list.");

            var buffer = new char[(int)requiredChars];
            guid = InterfaceClassGuid;
            status = CM_Get_Device_Interface_ListW(ref guid, null, buffer, requiredChars, CmGetDeviceInterfaceListPresent);
            if (status != 0)
                return InsydeBridgeSnapshot.Unavailable($"Configuration Manager list query failed (CONFIGRET 0x{status:X8}).");

            var paths = new string(buffer)
                .Split((char)0, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(path => path.Contains("ACPI#CLV0001#", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            return new InsydeBridgeSnapshot(
                paths.Length > 0,
                paths.Length,
                paths.Length > 0
                    ? $"CLV0001 · {paths.Length} published device interface(s) · discovery only"
                    : "No present CLV0001 path was returned for this interface GUID.");
        }
        catch (DllNotFoundException)
        {
            return InsydeBridgeSnapshot.Unavailable("Windows Configuration Manager API (cfgmgr32.dll) is unavailable.");
        }
        catch (EntryPointNotFoundException)
        {
            return InsydeBridgeSnapshot.Unavailable("The required Configuration Manager interface-list API is unavailable.");
        }
        catch (Exception ex)
        {
            return InsydeBridgeSnapshot.Unavailable($"CLV0001 discovery failed: {ex.GetType().Name}: {ex.Message}");
        }
    }

    [DllImport("cfgmgr32.dll", EntryPoint = "CM_Get_Device_Interface_List_SizeW", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint CM_Get_Device_Interface_List_SizeW(out uint length, ref Guid interfaceClassGuid, string? deviceInstanceId, uint flags);

    [DllImport("cfgmgr32.dll", EntryPoint = "CM_Get_Device_Interface_ListW", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint CM_Get_Device_Interface_ListW(
        ref Guid interfaceClassGuid,
        string? deviceInstanceId,
        [Out, MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.U2, SizeParamIndex = 3)] char[] buffer,
        uint bufferLength,
        uint flags);
}

public sealed record InsydeBridgeSnapshot(bool IsPublished, int InterfaceCount, string Detail)
{
    public static InsydeBridgeSnapshot Unavailable(string detail) => new(false, 0, detail);
}
