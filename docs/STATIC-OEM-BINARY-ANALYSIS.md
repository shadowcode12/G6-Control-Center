# Static OEM binary analysis — GIGABYTE G6 KF

Analysis date: 2026-11-11. This note records static inspection of the owner's uploaded binaries and the second OEM sensor inventory. No vendor DLL was loaded, and no WMI method, IOCTL, ACPI _DSM or EC operation was executed during analysis.

## Machine-specific inventory

- AppX package: CLEVOCO.FnhotkeysandOSD 7.101.0.0.
- The report was collected with IsAdministrator = false; it is not the elevated pass requested for complete service-process module inspection.
- Processes captured: DCHUService.exe (PID 5104), HKClipSvc.exe (PID 4888), and FnKey.exe (PID 17068).
- FnKey.exe loaded GetProductdll.dll and InsydeDCHU.dll from the AppX package's FnKey root directory. It did not show CC40.exe or GetCurrentCpuSpeed.dll as loaded modules in this capture.
- root\WMI contained 1600 classes, but no CLEVO_GET class was found; querying that class returned Invalid class. Two generic Microsoft WMI ACPI mapper devices were present: ACPI\PNP0C14\OPT1 and ACPI\PNP0C14\0.
- ACPI\CLV0001\1: Insyde AcpiBridge, driver INF oem30.inf, version 1.0.0.7, service name AcpiBridge.
- ACPI\CLV0002\1: CLEVO Acpi Bridge1, driver INF oem70.inf, version 6.0.46.2, service CCDCHUService, image DCHUService.exe.

## Exact DLL identity and exports

### GetCurrentCpuSpeed.dll

File: FnKey\CC40\GetCurrentCpuSpeed.dll

SHA-256: C0273E8D9578C80CB6F44CBC95CA2444A6572D985A97A89053547282D4B80095

PE: x64 native DLL.

Exports:
- GetBaseSpeed
- GetCpuSpeed
- GetProcessorPerformance

Static imports include:
- PdhOpenQueryW
- PdhAddEnglishCounterW
- PdhCollectQueryData
- PdhGetFormattedCounterValue
- PdhCloseQuery
- COM/OLE APIs

Embedded strings include:
- \Processor Information(_Total)\% Processor Performance
- SELECT * FROM Win32_Processor
- MaxClockSpeed
- ROOT\CIMV2

The exported GetCpuSpeed calls GetProcessorPerformance and GetBaseSpeed and combines their results. This establishes a Windows PDH/WMI-based frequency path; it does not establish CPU temperature or fan-RPM access. G6 Control Center v0.4.0 implements an independent, read-only estimate using the Windows PDH Processor Performance counter and CPUID nominal/base frequency. The UI labels it as an estimate rather than a direct hardware sensor.

### InsydeDCHU.dll copies

Three distinct binaries were supplied:

| Package location / role | Size | SHA-256 | Signature |
|---|---:|---|---|
| FnKey\CC40\InsydeDCHU.dll | 2,492,416 | DAB807B5D4A621893EF5C5C1941E9D8CE91DDA6B2518E931F4BB4727DFD80E98 | Not signed |
| FnKey\DCHU\InsydeDCHU.dll | 2,503,032 | D385DEF14C5AA6CBB8EB60FD34D0EFEB92EAF39E875AB28DE05FE0FDAA7CAB9C | Valid CLEVO signature |
| Loaded by FnKey.exe from FnKey\InsydeDCHU.dll | 2,503,008 | 75A47020D3A9D052E94DCB4E3AD61FB69F20177DD46E20C9A20883D92B83981B | Not separately reported |

The legacy Program Files (x86)\ControlCenter\DCHU\InsydeDCHU.dll copy matched the DCHU-subfolder hash. Do not assume these three binaries are interchangeable. The actual file loaded by FnKey.exe is the third, distinct build.

The supplied InsydeDCHU variants export:
- GetDCHU_Data_Integer
- GetDCHU_Data_Buffer
- ReadAppSettings
- SetDCHU_Data
- SetDCHU_DataEx
- WriteAppSettings

Static imports include CM_Get_Device_Interface_ListW, CM_Get_Device_Interface_List_SizeW, CreateFileW, DeviceIoControl, ReadFile, WriteFile, and CloseHandle. The binary contains the native PDB path D:\LOCAL_SOURCE_CODE\InsydeDCHU_dll\x64\Release\InsydeDCHU.pdb.

Static disassembly of GetDCHU_Data_Integer shows construction of an ACPI _DSM method argument payload and a DeviceIoControl call using control code 0x322400. This is a firmware/driver communication path, not a generic passive sensor read. Without verified per-command input/output semantics and exact G6 KF firmware behavior, G6 Control Center must not invoke these exports yet.

### DCHUService.exe

File SHA-256: 203B7CBD45635061932A032420656FF98036A5D97D5A3B44C9565D5957EF5CB0

Version: 6.0.46.0. PE: x64 .NET/CLR console-service executable.

Embedded strings include:
- CLEVO_GET.InstanceName='ACPI\PNP0C14\0_0'
- GetCPUtemp, GetCPUtempThermalIC
- GetVGA1temp, GetVGA2temp
- GetVGA1tempThermalIC, GetVGA2tempThermalIC
- GetCPUFANControl, GetCPUFANDuty, GetCPUFANState
- GetVGA1FANDuty, GetVGA2FANDuty
- GetFan12RPM, GetFan34RPM, GetFANCount, GetFanStatus
- Fan1Info, Fan2Info, Fan3Info, Fan4Info
- GetDCHU_Data_Buffer, GetDCHU_Data_Integer
- ACPIBIOS_READ, ACPIBIOS_WRITE, IOCTL_ACPIBIOS_READ_METHOD, DEVINTERFACE_ACPI_BRIDGE
- Setter names including SetFanDuty, SetFanAutoDuty, SetCPUFANControl, SetCPUPerformance, CPU/GPU voltage and power-limit setters.

These are string-table observations, not proof that each method is registered or callable on this firmware. The live root\WMI class query did not find CLEVO_GET, so do not invoke these names based only on strings.

### GetProductdll.dll and NVGPU_DLL.dll

- GetProductdll.dll exports product/platform and device-identification functions such as CheckClevo, GetProductID, GetProductID_PCI, GetDocking, and touchpad/fingerprint checks. The loaded FnKey build additionally exports VGA SSID/SVID queries. These are not CPU temperature or fan telemetry functions.
- NVGPU_DLL.dll contains NVIDIA monitoring exports such as Get_GPU_Temp, Get_GPU_Util, Get_GPU_Graphics_Clock, Get_GPU_Memory_Clock, Get_GPU_Volt, Get_GPU_ALLInfo, and CheckGPU_Thermal. It also contains overclocking, locking, thermal-limit and other setter exports. G6 Control Center will continue using the NVIDIA driver's read-only nvidia-smi query path instead of loading this OEM DLL.

## Engineering decisions

1. Use the confirmed Windows PDH/CPUID path for a labelled effective CPU frequency estimate.
2. Keep CPU temperature and fan RPM unavailable until their exact firmware/driver query is mapped.
3. Treat CLV0001 (Insyde AcpiBridge) and CLV0002 (CLEVO DCHUService) as separate device interfaces.
4. Do not invoke GetDCHU_Data_Integer, GetDCHU_Data_Buffer, any CLEVO_GET method, DeviceIoControl, ACPI _DSM, or fan setters during discovery.
5. Obtain a full elevated module inventory with the OEM UI open before considering dynamic tracing. The current second inventory is not elevated and only captured FnKey.exe's loaded modules.
