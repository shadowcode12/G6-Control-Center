# Read-only enumeration of the Insyde CLV0001 device interface.
# This only asks Windows Configuration Manager for published interface paths.
# It does NOT open a device handle, send IOCTLs, call ACPI _DSM, or touch EC/SMBus.

$ErrorActionPreference = "Stop"
$interfaceGuid = [Guid]"86994c74-ad43-4812-b7e7-0c420b5c5fd7"

if (-not ("G6CfgMgrInterfaceList" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class G6CfgMgrInterfaceList
{
    [DllImport("cfgmgr32.dll",
        EntryPoint = "CM_Get_Device_Interface_List_SizeW",
        CharSet = CharSet.Unicode,
        ExactSpelling = true)]
    public static extern uint CM_Get_Device_Interface_List_SizeW(
        out uint length,
        ref Guid interfaceClassGuid,
        string deviceInstanceId,
        uint flags);

    [DllImport("cfgmgr32.dll",
        EntryPoint = "CM_Get_Device_Interface_ListW",
        CharSet = CharSet.Unicode,
        ExactSpelling = true)]
    public static extern uint CM_Get_Device_Interface_ListW(
        ref Guid interfaceClassGuid,
        string deviceInstanceId,
        [Out, MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.U2, SizeParamIndex = 3)]
        char[] buffer,
        uint bufferLength,
        uint flags);
}
'@
}

# CM_GET_DEVICE_INTERFACE_LIST_PRESENT = 0x00000000
$flags = [uint32]0
[uint32]$requiredChars = 0

$sizeResult = [G6CfgMgrInterfaceList]::CM_Get_Device_Interface_List_SizeW(
    [ref]$requiredChars,
    [ref]$interfaceGuid,
    $null,
    $flags
)

if ($sizeResult -ne 0) {
    throw "CM_Get_Device_Interface_List_SizeW failed: CONFIGRET=$sizeResult"
}

$paths = @()
$listResult = [uint32]0

if ($requiredChars -gt 1) {
    $buffer = [char[]]::new([int]$requiredChars)

    $listResult = [G6CfgMgrInterfaceList]::CM_Get_Device_Interface_ListW(
        [ref]$interfaceGuid,
        $null,
        $buffer,
        $requiredChars,
        $flags
    )

    if ($listResult -ne 0) {
        throw "CM_Get_Device_Interface_ListW failed: CONFIGRET=$listResult"
    }

    $multiSz = -join $buffer
    $paths = @(
        [regex]::Split($multiSz, "\0+") |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
}

$device = $null
try {
    $device = Get-PnpDevice -InstanceId "ACPI\CLV0001\1" -ErrorAction Stop |
        Select-Object Status, Class, FriendlyName, InstanceId
} catch {
    $device = [pscustomobject]@{
        Status = "PnpDevice query unavailable"
        Class = $null
        FriendlyName = $null
        InstanceId = "ACPI\CLV0001\1"
    }
}

$result = [pscustomobject]@{
    InterfaceClassGuid = $interfaceGuid.ToString()
    DeviceInstanceId = "ACPI\CLV0001\1"
    Device = $device
    ConfigManagerResult = $listResult
    PublishedInterfaceCount = $paths.Count
    InterfacePaths = $paths
    Meaning = if ($paths.Count -gt 0) {
        "Windows publishes the CLV0001 interface. This confirms discovery only; it does not prove that the current process has permission or that a telemetry request is safe."
    } else {
        "No present interface path was returned for this GUID. Check the CLV0001 device and driver installation; no device IO was attempted."
    }
}

$result | Format-List
if ($paths.Count -gt 0) {
    Write-Host ([Environment]::NewLine + "Published interface paths:") -ForegroundColor Cyan
    $paths | ForEach-Object { Write-Host "  $_" }
}

Write-Host ([Environment]::NewLine + "Read-only discovery only: no CreateFile, DeviceIoControl, WMI method, ACPI _DSM or EC access was performed.") -ForegroundColor Green
