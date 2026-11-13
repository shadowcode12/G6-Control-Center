# Read-only metadata for the CLV0001 Insyde AcpiBridge driver.
# Does not open the device, send IOCTLs, invoke ACPI _DSM, or access EC/SMBus.

$ErrorActionPreference = "Continue"
$instanceId = "ACPI\CLV0001\1"

Write-Host "=== CLV0001 PnP device ===" -ForegroundColor Cyan
Get-PnpDevice -InstanceId $instanceId -ErrorAction SilentlyContinue |
    Format-List Status, Class, FriendlyName, InstanceId

Write-Host "=== Driver properties ===" -ForegroundColor Cyan
$keys = @(
    "DEVPKEY_Device_Service",
    "DEVPKEY_Device_DriverInfPath",
    "DEVPKEY_Device_DriverVersion",
    "DEVPKEY_Device_DriverProvider",
    "DEVPKEY_Device_DriverDesc",
    "DEVPKEY_Device_DriverDate",
    "DEVPKEY_Device_HardwareIds"
)
foreach ($key in $keys) {
    $prop = Get-PnpDeviceProperty -InstanceId $instanceId -KeyName $key -ErrorAction SilentlyContinue
    if ($null -ne $prop) {
        "{0} = {1}" -f $key, (($prop.Data | ForEach-Object { $_ }) -join "; ")
    }
}

Write-Host ([Environment]::NewLine + "=== AcpiBridge service ===") -ForegroundColor Cyan
$service = Get-CimInstance Win32_SystemDriver -Filter "Name='AcpiBridge'" -ErrorAction SilentlyContinue
if ($service) {
    $service | Format-List Name, DisplayName, State, Started, StartMode, ServiceType, PathName
    $rawPath = [Environment]::ExpandEnvironmentVariables([string]$service.PathName).Trim('"')
    $driverPath = $rawPath

    if ($rawPath.StartsWith("\SystemRoot\", [StringComparison]::OrdinalIgnoreCase)) {
        $driverPath = Join-Path $env:windir $rawPath.Substring(12)
    } elseif ($rawPath.StartsWith("System32\", [StringComparison]::OrdinalIgnoreCase)) {
        $driverPath = Join-Path $env:windir $rawPath
    }

    Write-Host ([Environment]::NewLine + "Resolved driver path: " + $driverPath)
    if (Test-Path -LiteralPath $driverPath -PathType Leaf) {
        $file = Get-Item -LiteralPath $driverPath
        $hash = Get-FileHash -LiteralPath $driverPath -Algorithm SHA256
        $signature = Get-AuthenticodeSignature -FilePath $driverPath
        [pscustomobject]@{
            Path = $driverPath
            SizeBytes = $file.Length
            FileVersion = $file.VersionInfo.FileVersion
            ProductVersion = $file.VersionInfo.ProductVersion
            Company = $file.VersionInfo.CompanyName
            SHA256 = $hash.Hash
            SignatureStatus = [string]$signature.Status
            Signer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
        } | Format-List
    } else {
        Write-Warning "Driver file was not found at the resolved service path."
    }
} else {
    Write-Warning "Win32_SystemDriver did not return a service named AcpiBridge."
}

Write-Host ([Environment]::NewLine + "=== Matching installed driver packages ===") -ForegroundColor Cyan
pnputil.exe /enum-drivers /class System |
    Select-String -Pattern "oem30.inf|AcpiBridge|Insyde|Driver Version|Original Name|Provider Name" -Context 1,2

Write-Host ([Environment]::NewLine + "Read-only metadata only. No device open, IOCTL, WMI method, ACPI _DSM or EC operation was performed.") -ForegroundColor Green
