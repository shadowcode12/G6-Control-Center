# Read-only inventory of the OEM Clevo/Insyde sensor interface.
# This script does NOT invoke WMI methods, load vendor DLLs, call DeviceIoControl,
# access ACPI _DSM, or write to EC/SMBus.

$ErrorActionPreference = "Continue"
$OutDir = Join-Path $env:USERPROFILE "Desktop\G6-RE"
$OutFile = Join-Path $OutDir "OEM-Sensor-Inventory.txt"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$report = [ordered]@{
    GeneratedAt = (Get-Date).ToString("o")
    Package = @()
    Services = @()
    Processes = @()
    LoadedModules = @()
    AcpiDevices = @()
    WmiClasses = @()
    WmiInstances = @()
    CandidateBinaries = @()
    Errors = @()
}

try {
    $packages = @(Get-AppxPackage -Name "CLEVOCO.FnhotkeysandOSD" -ErrorAction Stop)
    $report.Package = @($packages | Select-Object Name, Version, PackageFullName, InstallLocation)
} catch {
    $report.Errors += "Appx package query: $($_.Exception.Message)"
}

$installRoot = $null
if ($report.Package.Count -gt 0) {
    $installRoot = $report.Package[0].InstallLocation
}

$cc40Root = if ($installRoot) { Join-Path $installRoot "FnKey\CC40" } else { $null }
$dchuRoot = if ($installRoot) { Join-Path $installRoot "FnKey\DCHU" } else { "C:\Program Files (x86)\ControlCenter\DCHU" }

try {
    $report.Services = @(
        Get-CimInstance Win32_Service |
        Where-Object {
            $_.Name -match "DCHU|HKClip" -or
            $_.DisplayName -match "Control Center Hotkey|HotKey Clipboard"
        } |
        Select-Object Name, DisplayName, State, StartMode, PathName
    )
} catch {
    $report.Errors += "Service query: $($_.Exception.Message)"
}

try {
    $report.Processes = @(
        Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match "^(CC40|DCHUService|HKClipSvc)\.exe$" } |
        Select-Object Name, ProcessId, ExecutablePath, CommandLine
    )

    foreach ($entry in $report.Processes) {
        try {
            $proc = Get-Process -Id ([int]$entry.ProcessId) -ErrorAction Stop
            foreach ($module in $proc.Modules) {
                $report.LoadedModules += [pscustomobject]@{
                    Process = $entry.Name
                    PID = $entry.ProcessId
                    Module = $module.ModuleName
                    Path = $module.FileName
                }
            }
        } catch {
            $report.Errors += "Module list for PID $($entry.ProcessId): $($_.Exception.Message)"
        }
    }
} catch {
    $report.Errors += "Process query: $($_.Exception.Message)"
}

try {
    $report.AcpiDevices = @(
        Get-PnpDevice -PresentOnly |
        Where-Object { $_.InstanceId -match "^ACPI\\CLV000[12]" } |
        Select-Object Status, Class, FriendlyName, InstanceId, Problem
    )
} catch {
    $report.Errors += "PnP query: $($_.Exception.Message)"
}

# Discover the WMI class and its method/property signatures only.
# No CLEVO_GET methods are invoked by this script.
try {
    $classes = @(Get-CimClass -Namespace "root\WMI" |
        Where-Object { $_.CimClassName -match "CLEVO|DCHU" })

    foreach ($class in $classes) {
        $methodRows = @()
        foreach ($method in $class.CimClassMethods) {
            $parameters = @()
            foreach ($parameter in $method.Parameters) {
                $parameters += "$($parameter.Name):$($parameter.CimType)"
            }
            $methodRows += [pscustomobject]@{
                Name = $method.Name
                ReturnType = [string]$method.ReturnType
                Parameters = ($parameters -join ", ")
            }
        }

        $propertyRows = @()
        foreach ($property in $class.CimClassProperties) {
            $propertyRows += [pscustomobject]@{
                Name = $property.Name
                Type = [string]$property.CimType
            }
        }

        $report.WmiClasses += [pscustomobject]@{
            Namespace = "root\WMI"
            Name = $class.CimClassName
            Methods = $methodRows
            Properties = $propertyRows
        }

        try {
            $instances = @(Get-CimInstance -Namespace "root\WMI" -ClassName $class.CimClassName)
            foreach ($instance in $instances) {
                $report.WmiInstances += [pscustomobject]@{
                    Class = $class.CimClassName
                    InstanceName = $instance.InstanceName
                    Data = $instance.Data
                }
            }
        } catch {
            $report.Errors += "WMI instance $($class.CimClassName): $($_.Exception.Message)"
        }
    }
} catch {
    $report.Errors += "WMI class discovery: $($_.Exception.Message)"
}

$paths = @()
if ($cc40Root) {
    $paths += (Join-Path $cc40Root "CC40.exe")
    $paths += (Join-Path $cc40Root "InsydeDCHU.dll")
    $paths += (Join-Path $cc40Root "GetCurrentCpuSpeed.dll")
    $paths += (Join-Path $cc40Root "GetProductdll.dll")
    $paths += (Join-Path $cc40Root "NVGPU_DLL.dll")
}
if ($dchuRoot) {
    $paths += (Join-Path $dchuRoot "InsydeDCHU.dll")
    $paths += (Join-Path $dchuRoot "GetProductdll.dll")
}
$paths += "C:\Program Files (x86)\ControlCenter\DCHU\InsydeDCHU.dll"

foreach ($path in ($paths | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    try {
        $file = Get-Item -LiteralPath $path
        $version = $file.VersionInfo
        $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256
        $signature = Get-AuthenticodeSignature -FilePath $path
        $report.CandidateBinaries += [pscustomobject]@{
            Path = $path
            Length = $file.Length
            FileVersion = $version.FileVersion
            ProductVersion = $version.ProductVersion
            Company = $version.CompanyName
            SHA256 = $hash.Hash
            SignatureStatus = [string]$signature.Status
            Signer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
        }
    } catch {
        $report.Errors += "Binary metadata $path : $($_.Exception.Message)"
    }
}

$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutFile -Encoding UTF8
Write-Host "Saved OEM sensor inventory: $OutFile" -ForegroundColor Green
Write-Host "This script only queried metadata, process modules, PnP devices and WMI class/instance inventory."
Write-Host "It did NOT invoke a CLEVO_GET method or write to firmware/hardware."
