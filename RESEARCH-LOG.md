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
- root\WMI had 1600 classes but no CLEVO_GET class; the explicit query returned Invalid class. Two Microsoft WmiAcpi PNP0C14 devices were found. No WMI method was invoked.
- DCHUService.exe contains string literals for CLEVO_GET.InstanceName='ACPI\PNP0C14\0_0' and fan/temperature method names (GetCPUtemp, GetVGA1temp, GetFan12RPM, GetFan34RPM, Fan1Info through Fan4Info), as well as setter names. These strings do not establish live WMI class registration or method compatibility.
- GetCurrentCpuSpeed.dll exports GetBaseSpeed, GetCpuSpeed and GetProcessorPerformance, and imports PDH query/counter APIs. Its embedded strings identify the Processor Information % Processor Performance counter and Win32_Processor MaxClockSpeed WMI property. This confirms a Windows PDH/WMI frequency path separate from DCHU.
- InsydeDCHU.dll exports GetDCHU_Data_Integer/GetDCHU_Data_Buffer and setters. Static disassembly of GetDCHU_Data_Integer shows an ACPI _DSM request passed through DeviceIoControl (control code 0x322400). Do not invoke until exact G6 KF arguments and side effects are validated.
- The actually loaded FnKey-root InsydeDCHU.dll is a third distinct hash; it must not be assumed byte-identical to the CC40 or DCHU-subfolder copies.
