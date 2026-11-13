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


## New findings from the supplied driver package (2026-11-13)

### CLV0001 is the strongest device-interface lead

The supplied INF_oem30.inf (Insyde, DriverVer 1.0.0.7) installs the ACPI\\CLV0001 device and registers this device-interface class GUID:

    {86994c74-ad43-4812-b7e7-0c420b5c5fd7}

The same INF associates a restricted custom device capability named Clevo.BiosDchuDriver_6h6z29zh29qx0 with that interface.

The supplied DCHUService.exe contains the exact interface path string:

    \\?\ACPI#CLV0001#1#{86994c74-ad43-4812-b7e7-0c420b5c5fd7}

The supplied InsydeDCHU.dll variants import CM_Get_Device_Interface_List_SizeW, CM_Get_Device_Interface_ListW, CreateFileW, and DeviceIoControl. These three independent observations (INF interface registration, service path string, DLL imports) point to the CLV0001/Insyde interface as the first path to validate. This is a stronger machine-specific lead than the absent generic CLEVO_GET WMI class.

### CLV0002 package is a separate component

The supplied INF_oem70.inf / acpibridge1.inf installs ACPI\\CLV0002 and copies AcpiBridge1.sys, DCHUService.exe, InsydeDCHU.dll, and other package files. Its service-install section registers CCDCHUService with ServiceType=0x10 (Win32 own-process service) and ServiceBinary=%13%\\DCHUService.exe. The value 0x10 is not the kernel-driver service type.

The supplied AcpiBridge1.sys is an x64 native Windows kernel binary built with KMDF. Its import table includes IoWMIRegistrationControl, MmGetSystemRoutineAddress, and WDF binding functions; it also has a local PDB path referencing AcpiBridge1\\x64\\Release. This establishes that the package contains a separate KMDF/WMI-related driver component, but does not by itself establish which fan/temperature data it exposes.

### DCHUService evidence

The supplied DCHUService.exe is an x64 Windows console-subsystem managed (.NET CLR-header) executable. Its static strings include:

- DEVINTERFACE_ACPI_BRIDGE
- the CLV0001 interface path above
- DeviceIoControl1, DeviceIoControl2, GetDCHU_Data_Buffer, and GetDCHU_Data_Integer
- root\\WMI, CLEVO_GET.InstanceName='ACPI\\PNP0C14\\0_0', and WMI helper strings
- CPU/GPU temperature and fan method names, along with several setter names

The live inventory still reports CLEVO_GET as an invalid class. Static strings are not proof that the WMI class is registered on this firmware. The CLV0001 interface path is therefore the better next discovery target, while the WMI route remains unconfirmed.

### AMD driver files in the CLEVO package

The supplied AMDRyzenMasterDriver.inf targets Root\\AMDRMDRIVER and is explicitly grouped under an AMD section in the CLEVO package INF. The owner's processor is Intel Core i7-13620H. These files are package contents for an AMD platform variant and are not a sensor driver to install or load on this Intel laptop.

### Next safe test

Run tools/Test-InsydeBridgeDiscovery.ps1. It calls only Windows Configuration Manager's interface-list APIs for the published CLV0001 GUID and prints any present interface paths. It does not open the device or issue any IOCTL/ACPI/EC requests. Paste the console output; no additional file upload is needed.
## CLV0001 interface presence confirmed on the user's G6 KF (2026-11-13)

- The user ran the Configuration Manager discovery tool: ACPI\\CLV0001\\1 returned Status OK; CONFIGRET 0; one published path was returned for GUID 86994c74-ad43-4812-b7e7-0c420b5c5fd7.
- This confirms Windows publishes the Insyde bridge interface. It does not confirm that the app can open the device or that any IOCTL/ACPI request is safe.

### Exact Insyde DLL control flow from local static disassembly

- The actually-loaded FnKey-root InsydeDCHU.dll (SHA-256 75A47020D3A9D052E94DCB4E3AD61FB69F20177DD46E20C9A20883D92B83981B) exports GetDCHU_Data_Integer at RVA 0x2680 and GetDCHU_Data_Buffer at RVA 0x2D50.
- A shared helper enumerates the CLV0001 interface GUID and opens the device with CreateFileW. Static code supplies desired access 0xC0000000 (read/write) and share mode 3.
- Both getters construct an ACPI _DSM request with UUID 93f224e4-fbdc-4bbf-add6-db71bdc0afad, the caller-supplied command integer and package argument data.
- Both call DeviceIoControl with private control code 0x322400. The driver handler's minimum buffer requirements and an independent matching implementation indicate input length 0x420 and output length 0x40C; an earlier local note had these directions reversed and is corrected here.
- GetDCHU_Data_Buffer parses returned ACPI package buffer elements and copies bytes to the caller's output buffer. Its command ID is supplied by the caller; the export does not hard-code command 12.
- This is static evidence, not a runtime test. The getter uses a read/write handle and sends a firmware ACPI request; do not invoke until the exact command and G6 KF firmware side effects are approved.

### Distinguish the two bridge drivers

- oem30.inf installs ACPI\\CLV0001 and references AcpiBridge.sys as a kernel driver (ServiceType=1, demand start). This is the CLV0001 driver whose interface is now confirmed published.
- Uploaded DriverStore_AcpiBridge1.sys belongs to the separate oem70.inf package for ACPI\\CLV0002; it is not the CLV0001 AcpiBridge.sys binary.
- The installed CLV0001 AcpiBridge.sys path/hash/version/signature have not yet been captured. tools/Get-Clv0001DriverInfo.ps1 prints those fields locally so the user can paste output without uploading a binary.

### External comparison — different Clevo model

- Separate NH5xAx Clevo reverse-engineering notes document the same CLV0001 interface GUID and a fan telemetry call GetDCHU_Data_Buffer(12). The report says package 12 invokes an ACPI _DSM path that issues EC command 0xC0 and returns a 256-byte telemetry buffer.
- This is a useful candidate mapping but was validated on another Clevo model; it is not yet confirmed on the G6 KF. Source: https://github.com/samoylenkodmitry/clevo-thermald/blob/main/docs/REVERSE-ENGINEERING.md

### Current safe boundary

The app checks only whether the CLV0001 device-interface path is published. It does not call CreateFileW, DeviceIoControl, GetDCHU_Data_Buffer, GetDCHU_Data_Integer, ACPI _DSM or any fan setter.

### Buffer-direction correction (2026-11-13)

The prior sentence in this document incorrectly labelled the 0x322400 DeviceIoControl buffers as input 0x40C / output 0x420. Static inspection of the exact CLV0001 AcpiBridge.sys shows WdfRequestRetrieveInputBuffer minimum 0x420 and WdfRequestRetrieveOutputBuffer minimum 0x14. A separate implementation of this same protocol explicitly allocates EvalInputSize=0x420 and EvalOutputSize=0x40C. Therefore the best-supported direction is **input 0x420, output 0x40C**. The earlier labels were transposed. Re-check the exact DLL callsite if that binary is available again before treating its call arguments as independently verified.


### Verified App Store operation layout (2026-11-13)

Static analysis of the exact installed AcpiBridge.sys handler for IOCTL 0x32240C indicates:
- A 4 KiB backing store (maximum extent 0x1000).
- 12-byte minimum input buffer and 4-byte minimum output buffer.
- DWORD operation selector 0 = read/copy out; selector 1 = write/copy in; other values rejected with 0xC0000030.
- Two 16-bit request fields at offsets +4 and +6 represent transfer offset and length; read validates output capacity and clamps to the backing-store boundary, while write validates offset+length and requires input size for an 8-byte header plus payload.
- This is a separate app-settings IOCTL and does not itself expose thermal/fan telemetry.

### ACPI input structure signature

The 0x322400 internal method helper writes the exact standard Windows ACPI_EVAL_INPUT_BUFFER_COMPLEX_SIGNATURE ('CieA', DWORD 0x43696541) before populating the ACPI complex input structure. It writes the caller's method selector into the MethodNameAsUlong field and constructs a first ACPI_METHOD_ARGUMENT with Type=2 (BUFFER) and DataLength=16, consistent with a UUID argument. Subsequent argument fields are populated from the supplied _DSM request, but the full nested package/buffer layout still awaits the remainder of the helper body (0x3500–0x3760).

See Microsoft's ACPI_EVAL_INPUT_BUFFER_COMPLEX structure: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/acpiioct/ns-acpiioct-_acpi_eval_input_buffer_complex_v1
See the Windows SDK signature definition: https://github.com/tpn/winsdk-10/blob/master/Include/10.0.16299.0/shared/acpiioct.h
