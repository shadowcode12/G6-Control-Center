# OEM and hardware-sensor research log

## Scope

Understand the installed GIGABYTE/CLEVO application architecture on the owner's G6 KF to inform an independent implementation. Do not copy OEM implementation code, redistribute OEM binaries, patch installed executables, or issue unknown hardware writes.

## Observed evidence

- The visible system interface includes System, FlexiCharger, LED Keyboard and Flexikey modules.
- The installed `CLEVOCO.FnhotkeysandOSD` package is x64 and contains a `FnKey\\CC40\\CC40.exe` application.
- The inspected `CC40.exe` is a PE32+ x64 executable with CLR metadata; its package contains WPF-related assemblies, Actipro WPF assemblies and GalaSoft MVVM Light assemblies.
- The package contains multiple native libraries and helper executables, including names associated with DCHU, HID, NVIDIA, keyboard LED and Intel tuning functionality.
- `DCHUService.exe` is registered as the Control Center Hotkey Service. `HKClipSvc.exe` is also present in the ControlCenter driver folder.
- The owner's WMI diagnostic returned no `MSAcpi_ThermalZoneTemperature` instances and no `Win32_Fan` instances. It identified the processor as Intel Core i7-13620H; `CurrentClockSpeed` and `MaxClockSpeed` both returned 2400 MHz, but this WMI snapshot is not treated as live per-core frequency telemetry.
- The G6 Control Center v0.3.0 screenshot showed NVIDIA telemetry working, while LibreHardwareMonitor did not expose CPU temperature, CPU core clocks or fan RPM. CPU package power appeared as 0.0 W; v0.3.1 filters non-positive package-power values as unavailable.

## Sensor-source evaluation

- LibreHardwareMonitor's official project documents support for Intel/AMD CPUs, NVIDIA/AMD/Intel GPUs, motherboards and network/storage devices, and provides a .NET 10-compatible library.
- Its documentation states that some sensors require Administrator privileges and hardware readout methods vary by manufacturer.
- G6 Control Center integrates LibreHardwareMonitorLib 0.9.6 for read-only discovery only. It does not automatically elevate itself.
- Version 0.3.1 writes a one-time hardware/sensor inventory to `%LOCALAPPDATA%\\G6ControlCenter\\Logs\\hardware-sensors.log`, recording the process elevation state and sensor names/types/values.
- A supported sensor library does not guarantee that this exact G6 KF exposes CPU temperature or fan RPM through the library. Results must be validated on the laptop.

## Important limitations

- A bundled DLL does not prove that every feature is active on this laptop or called by CC40 at runtime.
- Function names and imports are leads, not a complete hardware protocol specification.
- Fan control, EC writes, power limits, GPU switching and battery thresholds remain unimplemented until model-specific capabilities and safe bounds are established.
- Do not run unverified IOCTLs or write arbitrary EC/ACPI values.
- Do not treat a missing WMI or third-party sensor as proof that the hardware has no sensor; it may simply not be exposed through that software provider.

## Next research tasks

1. Inspect the v0.3.1 hardware inventory generated on the G6 KF.
2. Compare sensor availability in a one-time elevated diagnostic run; do not set permanent elevation.
3. Compare temperatures with an independent trusted sensor application under idle and controlled load.
4. Determine whether the original vendor service exposes read-only CPU and fan telemetry.
5. Determine which features can be implemented using documented Windows APIs and which require a signed vendor driver or firmware support.

## OEM communication-path investigation (2026-11-11)

- Static inspection of the user's uploaded CC40.exe string tables found InsydeDCHU.dll, GetCurrentCpuSpeed.dll, GetProductdll.dll, NVGPU_DLL.dll, GetDCHU_Data_Integer, GetDCHU_Data_Buffer, SetDCHU_Data, SetDCHU_DataEx, ReadAppSettings, and WriteAppSettings.
- The same binary contains UI identifiers T_CPUFan_RPM_value, T_GPUFan_RPM_value, T_cpu_temp_value, and CPU_Clock_Value.
- The package inventory places GetCurrentCpuSpeed.dll and InsydeDCHU.dll beside CC40.exe. A second InsydeDCHU.dll exists in the package's DCHU subfolder.
- The owner's service inventory shows DCHUService.exe running as Control Center Hotkey Service from the DriverStore.
- OEM screenshots from the exact G6 KF show CPU temperature, CPU clock and two fan RPM/duty values even though WMI and LibreHardwareMonitor did not expose those readings.
- A separate public Clevo model analysis documents a possible root/WMI / CLEVO_GET service interface and read-oriented fan getter command names, separate from setter commands 104/105. This is a candidate to validate, not assumed compatible with the G6 KF.
- That external report warns that its package-12 fan telemetry query writes EC command/data registers as part of the ACPI read transaction. G6 Control Center will not invoke that path until compatibility and side effects are understood and the owner explicitly approves a probe.

## Exact OEM binary analysis (2026-11-11)

- The second evidence collection was still non-elevated (IsAdministrator=false). It captured DCHUService.exe, HKClipSvc.exe and FnKey.exe; FnKey.exe loaded GetProductdll.dll and InsydeDCHU.dll from the AppX package's FnKey root. It did not capture CC40.exe or GetCurrentCpuSpeed.dll as loaded modules.
- The package has separate bridge devices: CLV0001 maps to Insyde AcpiBridge through oem30.inf (1.0.0.7); CLV0002 maps to CLEVO Acpi Bridge1 through oem70.inf (6.0.46.2) and CCDCHUService/DCHUService.exe.
- root\\WMI had 1600 classes but no CLEVO_GET class; the explicit query returned Invalid class. Two Microsoft WmiAcpi PNP0C14 devices were found. No WMI method was invoked.
- DCHUService.exe contains string literals for CLEVO_GET.InstanceName='ACPI\\PNP0C14\\0_0' and fan/temperature method names (GetCPUtemp, GetVGA1temp, GetFan12RPM, GetFan34RPM, Fan1Info through Fan4Info), as well as setter names. These strings do not establish live WMI class registration or method compatibility.
- GetCurrentCpuSpeed.dll exports GetBaseSpeed, GetCpuSpeed and GetProcessorPerformance, and imports PDH query/counter APIs. Its embedded strings identify the Processor Information % Processor Performance counter and Win32_Processor MaxClockSpeed WMI property. This confirms a Windows PDH/WMI frequency path separate from DCHU.
- InsydeDCHU.dll exports GetDCHU_Data_Integer/GetDCHU_Data_Buffer and setters. Static disassembly of GetDCHU_Data_Integer shows an ACPI _DSM request passed through DeviceIoControl (control code 0x322400). Do not invoke until exact G6 KF arguments and side effects are validated.
- The actually loaded FnKey-root InsydeDCHU.dll is a third distinct hash; it must not be assumed byte-identical to the CC40 or DCHU-subfolder copies.

## Driver-package analysis (2026-11-13)

- oem30.inf identifies Insyde ACPI\\CLV0001 and registers device-interface GUID 86994c74-ad43-4812-b7e7-0c420b5c5fd7 with custom capability Clevo.BiosDchuDriver_6h6z29zh29qx0.
- DCHUService.exe embeds the exact corresponding path \\?\\ACPI#CLV0001#1#{86994c74-ad43-4812-b7e7-0c420b5c5fd7}.
- The supplied InsydeDCHU.dll variants import CM_Get_Device_Interface_List_SizeW, CM_Get_Device_Interface_ListW, CreateFileW, and DeviceIoControl. Together these point to the CLV0001 interface as the first path to validate.
- oem70.inf installs CLV0002 and registers CCDCHUService as a Win32 own-process service (ServiceType=0x10) whose service binary is DCHUService.exe.
- The supplied AcpiBridge1.sys is an x64 native KMDF binary with imports including IoWMIRegistrationControl; the exact telemetry contract it implements remains unproven.
- DCHUService.exe contains a CLR header and static strings for both the CLV0001 device-interface path and the absent-on-this-machine CLEVO_GET WMI class, plus CPU/GPU temperature and fan getter/setter names. These strings do not prove that the WMI class or any given method is live/compatible.
- The bundled AMDRyzenMasterDriver.inf targets Root\\AMDRMDRIVER and is included under an AMD package section; it is not appropriate to install/load for the owner's Intel i7-13620H.
- Added tools/Test-InsydeBridgeDiscovery.ps1 to enumerate only the CLV0001 interface path via Configuration Manager. It does not open the device or issue IOCTL/ACPI/EC requests.

## CLV0001 device-interface result and DLL disassembly (2026-11-13)

- The user ran Test-InsydeBridgeDiscovery.ps1: ACPI\\CLV0001\\1 returned Status OK; Configuration Manager result 0; one published interface path was returned for GUID 86994c74-ad43-4812-b7e7-0c420b5c5fd7.
- Local disassembly of the exact loaded FnKey-root InsydeDCHU.dll confirms that getters enumerate this GUID, then use CreateFileW with desired access 0xC0000000 (read/write) and share mode 3.
- GetDCHU_Data_Integer and GetDCHU_Data_Buffer construct an ACPI _DSM request with UUID 93f224e4-fbdc-4bbf-add6-db71bdc0afad and call DeviceIoControl with private control code 0x322400, input length 0x40C and output length 0x420.
- GetDCHU_Data_Buffer is generic: command ID is supplied by its caller. It parses ACPI package buffer values into a caller-provided output buffer.
- oem30.inf installs CLV0001 using AcpiBridge.sys as a kernel driver. Uploaded AcpiBridge1.sys belongs to oem70.inf/CLV0002, not CLV0001.
- A separate NH5xAx Clevo analysis documents command 12 as a live fan telemetry package that triggers EC command 0xC0. This is external, model-specific evidence, not yet confirmed for the G6 KF.
- Added an in-app, non-invasive CLV0001 interface status card and tools/Get-Clv0001DriverInfo.ps1 for local driver metadata.

## Verified installed CLV0001 driver metadata (2026-11-13)

- The user-provided local diagnostic output identifies the running PnP device as ACPI\\CLV0001\\1, FriendlyName "Acpi Bridge", Status OK and ConfigManagerResult 0.
- Its selected driver is Insyde's oem30.inf, version 1.0.0.7, dated 2021-09-01 05:30:00, with service name AcpiBridge (kernel driver, Running, demand/manual start).
- The loaded driver image path is C:\\Windows\\System32\\drivers\\AcpiBridge.sys; file and product versions are both 1.0.0.7, company metadata is Insyde Software Corporation, and the Authenticode signature is Valid with signer Microsoft Windows Hardware Compatibility Publisher.
- The user's local SHA-256 for AcpiBridge.sys is BE879AF2EF1BEAA3AD041C30ABD103C5E9E872D23EA8442B57682BB0D06EA153. This is the first exact identity for the CLV0001 kernel binary in this investigation; it is not the previously supplied AcpiBridge1.sys binary (CLV0002/oem70.inf).
- The earlier discovery script returned exactly one published interface path for GUID 86994c74-ad43-4812-b7e7-0c420b5c5fd7. Driver identity plus interface publication are now confirmed, but successful CreateFile access, IOCTL semantics, telemetry command IDs, firmware compatibility and side effects remain untested.
- Next safe step: obtain static PE metadata/imports/strings from this exact installed AcpiBridge.sys without opening the device or invoking driver requests.