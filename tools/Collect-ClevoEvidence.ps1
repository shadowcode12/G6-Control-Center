# Read-only evidence collector for the GIGABYTE G6 KF / CLEVO-Insyde stack.
# It inventories devices, services, WMI class metadata, process modules, INF files,
# and local vendor binary metadata. It DOES NOT invoke any WMI methods, load any
# vendor DLL, issue IOCTLs, call ACPI _DSM, or write to EC/SMBus.

[CmdletBinding()]
param(
    [string]$OutputDirectory = "$env:USERPROFILE\Desktop\G6-RE\OEM-Sensor-Evidence"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$BinaryDirectory = Join-Path $OutputDirectory "VendorBinaries"
$DriverDirectory = Join-Path $OutputDirectory "DriverFiles"
New-Item -ItemType Directory -Force -Path $BinaryDirectory, $DriverDirectory | Out-Null

$Report = [ordered]@{
    GeneratedAt = (Get-Date).ToString("o")
    IsAdministrator = $false
    Package = @()
    Services = @()
    ServiceRegistry = @()
    Processes = @()
    LoadedModules = @()
    AcpiDevices = @()
    WmiNamespaceClassCounts = @()
    RelevantWmiClasses = @()
    ClevoGetQuery = $null
    WmiErrors = @()
    DeviceProperties = @()
    DriverInfDetails = @()
    CandidateBinaries = @()
    Errors = @()
    Safety = @(
        "Inventory only. No custom WMI method was invoked.",
        "No vendor DLL was loaded into this PowerShell process.",
        "No DeviceIoControl, ACPI _DSM, EC/SMBus access, fan setter, or power setter was invoked.",
        "Vendor binaries are copied locally for static analysis only and must not be committed to the public Git repository."
    )
}

function Add-ErrorRecord {
    param([string]$Stage, [string]$Message)
    $script:Report.Errors += [pscustomobject]@{
        Stage = $Stage
        Message = $Message
    }
}

function Add-CandidateFile {
    param(
        [string]$Label,
        [string]$Path,
        [string]$DestinationDirectory
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    try {
        $item = Get-Item -LiteralPath $Path -ErrorAction Stop
        $hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop
        $signature = Get-AuthenticodeSignature -FilePath $Path -ErrorAction SilentlyContinue
        $version = $item.VersionInfo

        $copyName = ("{0}_{1}" -f ($Label -replace '[^A-Za-z0-9_-]', '_'), $item.Name)
        $destination = Join-Path $DestinationDirectory $copyName
        Copy-Item -LiteralPath $Path -Destination $destination -Force -ErrorAction Stop

        $signer = $null
        $signatureStatus = "Unavailable"
        if ($null -ne $signature) {
            $signatureStatus = [string]$signature.Status
            if ($null -ne $signature.SignerCertificate) {
                $signer = $signature.SignerCertificate.Subject
            }
        }

        $script:Report.CandidateBinaries += [pscustomobject]@{
            Label = $Label
            OriginalPath = $Path
            FileName = $item.Name
            Length = $item.Length
            FileVersion = $version.FileVersion
            ProductVersion = $version.ProductVersion
            Company = $version.CompanyName
            SHA256 = $hash.Hash
            SignatureStatus = $signatureStatus
            Signer = $signer
            LocalCopy = $destination
        }
    } catch {
        Add-ErrorRecord "Binary copy/metadata: $Path" $_.Exception.Message
    }
}

# Elevation state.
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    $Report.IsAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch {
    Add-ErrorRecord "Elevation" $_.Exception.Message
}

# Exact AppX package location.
$installRoot = $null
try {
    $package = Get-AppxPackage -Name "CLEVOCO.FnhotkeysandOSD" -ErrorAction Stop |
        Sort-Object Version -Descending |
        Select-Object -First 1

    if ($package) {
        $installRoot = $package.InstallLocation
        $Report.Package = @([pscustomobject]@{
            Name = $package.Name
            Version = $package.Version.ToString()
            PackageFullName = $package.PackageFullName
            InstallLocation = $package.InstallLocation
        })
    }
} catch {
    Add-ErrorRecord "AppX package" $_.Exception.Message
}

$cc40Root = if ($installRoot) { Join-Path $installRoot "FnKey\CC40" } else { $null }
$dchuRoot = if ($installRoot) { Join-Path $installRoot "FnKey\DCHU" } else { "C:\Program Files (x86)\ControlCenter\DCHU" }

# Services and their registry configuration.
try {
    $Report.Services = @(
        Get-CimInstance Win32_Service |
        Where-Object {
            $_.Name -match "DCHU|HKClip|AcpiBridge" -or
            $_.DisplayName -match "Control Center Hotkey|HotKey Clipboard|ACPI Bridge"
        } |
        Select-Object Name, DisplayName, State, StartMode, PathName
    )
} catch {
    Add-ErrorRecord "Service inventory" $_.Exception.Message
}

foreach ($service in $Report.Services) {
    try {
        $key = "HKLM:\SYSTEM\CurrentControlSet\Services\$($service.Name)"
        if (Test-Path $key) {
            $properties = Get-ItemProperty -LiteralPath $key
            $Report.ServiceRegistry += [pscustomobject]@{
                Name = $service.Name
                ImagePath = $properties.ImagePath
                Type = $properties.Type
                Start = $properties.Start
                DisplayName = $properties.DisplayName
                ParametersPath = Join-Path $key "Parameters"
            }
        }
    } catch {
        Add-ErrorRecord "Service registry $($service.Name)" $_.Exception.Message
    }
}

# Keep the OEM Control Center open while collecting so CC40.exe appears here.
try {
    $processRows = @(
        Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "(?i)(CC40|DCHUService|HKClipSvc|FnKey|cc30wk|FanSpeedSetting|ControlCenter|GIGABYTE|GCC|Flexi)" -or
            ($installRoot -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith($installRoot, [System.StringComparison]::OrdinalIgnoreCase))
        } |
        Select-Object Name, ProcessId, ExecutablePath, CommandLine
    )
    $Report.Processes = $processRows

    foreach ($row in $processRows) {
        if (-not $row.ProcessId) { continue }
        try {
            $proc = Get-Process -Id ([int]$row.ProcessId) -ErrorAction Stop
            foreach ($module in $proc.Modules) {
                $Report.LoadedModules += [pscustomobject]@{
                    ProcessName = $row.Name
                    ProcessId = $row.ProcessId
                    ModuleName = $module.ModuleName
                    FileName = $module.FileName
                }
            }
        } catch {
            Add-ErrorRecord "Loaded modules for PID $($row.ProcessId)" $_.Exception.Message
        }
    }
} catch {
    Add-ErrorRecord "Process/module inventory" $_.Exception.Message
}

# Discover CLV0001, CLV0002, and the ACPI WMI mapper device PNP0C14.
try {
    $deviceRows = @(
        Get-PnpDevice -PresentOnly -ErrorAction Stop |
        Where-Object {
            $_.InstanceId -match "^ACPI\\(CLV0001|CLV0002|PNP0C14)" -or
            $_.FriendlyName -match "ACPI Bridge|ACPI WMI|DCHU|Clevo"
        } |
        Select-Object Status, Class, FriendlyName, InstanceId, Problem
    )
    $Report.AcpiDevices = $deviceRows

    $propertyKeys = @(
        "DEVPKEY_Device_HardwareIds",
        "DEVPKEY_Device_Service",
        "DEVPKEY_Device_DriverInfPath",
        "DEVPKEY_Device_DriverVersion",
        "DEVPKEY_Device_DriverProvider",
        "DEVPKEY_Device_DriverDesc",
        "DEVPKEY_Device_Manufacturer",
        "DEVPKEY_Device_ClassGuid",
        "DEVPKEY_Device_UpperFilters",
        "DEVPKEY_Device_LowerFilters"
    )

    foreach ($device in $deviceRows) {
        $values = [ordered]@{
            InstanceId = $device.InstanceId
            FriendlyName = $device.FriendlyName
        }

        foreach ($keyName in $propertyKeys) {
            try {
                $property = Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName $keyName -ErrorAction Stop
                $values[$keyName] = $property.Data
            } catch {
                # Optional property; absence is not an error condition.
            }
        }

        $Report.DeviceProperties += [pscustomobject]$values
    }
} catch {
    Add-ErrorRecord "PnP device inventory" $_.Exception.Message
}

# WMI class metadata only. Enumerate root\WMI classes instead of assuming CLEVO_GET exists.
try {
    $allWmiClasses = @(Get-CimClass -Namespace "root\WMI" -ErrorAction Stop)
    $Report.WmiNamespaceClassCounts += [pscustomobject]@{
        Namespace = "root\WMI"
        ClassCount = $allWmiClasses.Count
    }

    $patterns = "CLEVO|DCHU|ACPI|FAN|THERM|PNP0C14|INSYDE"
    foreach ($class in ($allWmiClasses | Where-Object { $_.CimClassName -match $patterns })) {
        $methodRows = @()
        foreach ($method in $class.CimClassMethods) {
            $parameters = @()
            foreach ($parameter in $method.Parameters) {
                $parameters += [pscustomobject]@{
                    Name = $parameter.Name
                    CimType = [string]$parameter.CimType
                    Flags = [string]$parameter.Flags
                }
            }

            $methodRows += [pscustomobject]@{
                Name = $method.Name
                ReturnType = [string]$method.ReturnType
                Parameters = $parameters
            }
        }

        $propertyRows = @()
        foreach ($property in $class.CimClassProperties) {
            $propertyRows += [pscustomobject]@{
                Name = $property.Name
                CimType = [string]$property.CimType
                Flags = [string]$property.Flags
            }
        }

        $Report.RelevantWmiClasses += [pscustomobject]@{
            Namespace = "root\WMI"
            Name = $class.CimClassName
            Methods = $methodRows
            Properties = $propertyRows
        }
    }
} catch {
    $Report.WmiErrors += "Get-CimClass root\WMI: $($_.Exception.Message)"
}

# Cross-check using the legacy WMI API; still metadata/query only.
try {
    $legacyClasses = @(Get-WmiObject -Namespace "root\WMI" -List -ErrorAction Stop |
        Where-Object { $_.__CLASS -match "CLEVO|DCHU|ACPI|FAN|THERM|PNP0C14|INSYDE" })

    foreach ($legacyClass in $legacyClasses) {
        $Report.RelevantWmiClasses += [pscustomobject]@{
            Namespace = "root\WMI (legacy WMI enumeration)"
            Name = $legacyClass.__CLASS
            Methods = @($legacyClass.Methods | ForEach-Object {
                [pscustomobject]@{ Name = $_.Name; ReturnType = [string]$_.ReturnType }
            })
            Properties = @($legacyClass.Properties | ForEach-Object {
                [pscustomobject]@{ Name = $_.Name; CimType = [string]$_.Type }
            })
        }
    }
} catch {
    $Report.WmiErrors += "Get-WmiObject root\WMI list: $($_.Exception.Message)"
}

# Query the candidate instance without invoking methods.
try {
    $instances = @(Get-CimInstance -Namespace "root\WMI" -ClassName "CLEVO_GET" -ErrorAction Stop)
    $Report.ClevoGetQuery = [pscustomobject]@{
        Found = $true
        Count = $instances.Count
        Instances = @($instances | Select-Object InstanceName, Data)
    }
} catch {
    $Report.ClevoGetQuery = [pscustomobject]@{
        Found = $false
        Error = $_.Exception.Message
    }
}

# Resolve the INF(s) used by the ACPI device nodes and record selected directive lines.
$infPaths = @()
foreach ($device in $Report.DeviceProperties) {
    $infProperty = $device.PSObject.Properties["DEVPKEY_Device_DriverInfPath"]
    $infName = if ($null -ne $infProperty) { $infProperty.Value } else { $null }
    if (-not [string]::IsNullOrWhiteSpace([string]$infName)) {
        $fullInfPath = Join-Path "$env:windir\INF" ([string]$infName)
        if (Test-Path -LiteralPath $fullInfPath) {
            $infPaths += $fullInfPath
        }
    }
}

# DriverStore directory is obtained from the running DCHU service path.
$servicePaths = @($Report.Services | Where-Object { $_.Name -match "DCHU" -and $_.PathName } |
    ForEach-Object { $_.PathName })

foreach ($servicePath in $servicePaths) {
    $serviceExe = [regex]::Match($servicePath, '^\s*"?(.+?\.exe)"?(?:\s|$)', 'IgnoreCase').Groups[1].Value
    if ($serviceExe -and (Test-Path -LiteralPath $serviceExe)) {
        $driverStoreDirectory = Split-Path $serviceExe -Parent
        foreach ($fileName in @("acpibridge.inf","acpibridge1.inf","AcpiBridge.inf","AcpiBridge1.inf")) {
            $candidate = Join-Path $driverStoreDirectory $fileName
            if (Test-Path -LiteralPath $candidate) { $infPaths += $candidate }
        }

        foreach ($driverFile in (Get-ChildItem -LiteralPath $driverStoreDirectory -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in ".sys", ".inf", ".cat" })) {
            Add-CandidateFile -Label "DriverStore" -Path $driverFile.FullName -DestinationDirectory $DriverDirectory
        }

        Add-CandidateFile -Label "DriverStore" -Path $serviceExe -DestinationDirectory $BinaryDirectory
    }
}

foreach ($infPath in ($infPaths | Select-Object -Unique)) {
    try {
        $lines = @(Select-String -LiteralPath $infPath -Pattern "CLV0001|CLV0002|PNP0C14|AddService|ServiceBinary|DriverVer|Provider|ClassGuid|UpperFilters|LowerFilters" |
            ForEach-Object { $_.Line.Trim() })

        $Report.DriverInfDetails += [pscustomobject]@{
            Path = $infPath
            SHA256 = (Get-FileHash -LiteralPath $infPath -Algorithm SHA256).Hash
            RelevantLines = $lines
        }

        Add-CandidateFile -Label "INF" -Path $infPath -DestinationDirectory $DriverDirectory
    } catch {
        Add-ErrorRecord "INF inspection: $infPath" $_.Exception.Message
    }
}

# The package has separate CC40 and DCHU copies of InsydeDCHU.dll.
# Preserve both as separate files; do not assume same version means same protocol.
$candidates = @()
if ($cc40Root) {
    $candidates += [pscustomobject]@{ Label = "CC40"; Path = (Join-Path $cc40Root "GetCurrentCpuSpeed.dll") }
    $candidates += [pscustomobject]@{ Label = "CC40"; Path = (Join-Path $cc40Root "InsydeDCHU.dll") }
    $candidates += [pscustomobject]@{ Label = "CC40"; Path = (Join-Path $cc40Root "GetProductdll.dll") }
    $candidates += [pscustomobject]@{ Label = "CC40"; Path = (Join-Path $cc40Root "NVGPU_DLL.dll") }
}
if ($dchuRoot) {
    $candidates += [pscustomobject]@{ Label = "DCHU"; Path = (Join-Path $dchuRoot "InsydeDCHU.dll") }
    $candidates += [pscustomobject]@{ Label = "DCHU"; Path = (Join-Path $dchuRoot "GetProductdll.dll") }
}
$candidates += [pscustomobject]@{ Label = "LegacyDCHU"; Path = "C:\Program Files (x86)\ControlCenter\DCHU\InsydeDCHU.dll" }

foreach ($candidate in $candidates) {
    Add-CandidateFile -Label $candidate.Label -Path $candidate.Path -DestinationDirectory $BinaryDirectory
}

# Add app process's actually loaded copies when CC40 is open.
foreach ($module in $Report.LoadedModules) {
    if ($module.ModuleName -match "InsydeDCHU|GetCurrentCpuSpeed|GetProductdll|NVGPU_DLL") {
        Add-CandidateFile -Label "LoadedModule" -Path $module.FileName -DestinationDirectory $BinaryDirectory
    }
}

$jsonPath = Join-Path $OutputDirectory "OEM-Sensor-Inventory.json"
$textPath = Join-Path $OutputDirectory "OEM-Sensor-Inventory.txt"
$Report | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("G6 Control Center - OEM sensor inventory")
$lines.Add("Generated: $($Report.GeneratedAt)")
$lines.Add("Elevated: $($Report.IsAdministrator)")
$lines.Add("")
$lines.Add("APPX PACKAGE")
$lines.Add(($Report.Package | Format-List | Out-String).Trim())
$lines.Add("")
$lines.Add("SERVICES")
$lines.Add(($Report.Services | Format-Table -AutoSize | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("PROCESSES")
$lines.Add(($Report.Processes | Format-Table -AutoSize | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("LOADED MODULES")
$lines.Add(($Report.LoadedModules | Format-Table ProcessName, ModuleName, FileName -AutoSize | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("ACPI / PNP DEVICES")
$lines.Add(($Report.DeviceProperties | Format-List | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("WMI NAMESPACE CLASS COUNTS")
$lines.Add(($Report.WmiNamespaceClassCounts | Format-Table -AutoSize | Out-String).Trim())
$lines.Add("")
$lines.Add("RELEVANT WMI CLASSES / METHODS (METADATA ONLY)")
foreach ($class in $Report.RelevantWmiClasses) {
    $lines.Add("Class: $($class.Namespace):$($class.Name)")
    foreach ($method in $class.Methods) {
        $parameters = ($method.Parameters | ForEach-Object { "$($_.Name):$($_.CimType)" }) -join ", "
        $lines.Add("  Method: $($method.Name) -> $($method.ReturnType) ($parameters)")
    }
}
$lines.Add("")
$lines.Add("CLEVO_GET QUERY (NO METHODS INVOKED)")
$lines.Add(($Report.ClevoGetQuery | Format-List | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("WMI ERRORS")
$lines.Add(($Report.WmiErrors -join [Environment]::NewLine))
$lines.Add("")
$lines.Add("DRIVER INF DETAILS")
foreach ($inf in $Report.DriverInfDetails) {
    $lines.Add("INF: $($inf.Path)")
    $lines.Add("SHA256: $($inf.SHA256)")
    $lines.AddRange([string[]]$inf.RelevantLines)
}
$lines.Add("")
$lines.Add("CANDIDATE BINARIES")
$lines.Add(($Report.CandidateBinaries | Format-List | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("ERRORS")
$lines.Add(($Report.Errors | Format-Table -AutoSize | Out-String -Width 220).Trim())
$lines.Add("")
$lines.Add("SAFETY")
$lines.AddRange([string[]]$Report.Safety)
$lines | Set-Content -LiteralPath $textPath -Encoding UTF8

$zipPath = "$OutputDirectory.zip"
if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -Path (Join-Path $OutputDirectory "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "G6 KF OEM evidence collection complete." -ForegroundColor Green
Write-Host "JSON:     $jsonPath"
Write-Host "Text:     $textPath"
Write-Host "Binaries: $BinaryDirectory"
Write-Host "Drivers:  $DriverDirectory"
Write-Host "ZIP:      $zipPath"
Write-Host ""
Write-Host "No WMI method, OEM DLL function, IOCTL, ACPI _DSM, fan setter, or EC write was invoked."
