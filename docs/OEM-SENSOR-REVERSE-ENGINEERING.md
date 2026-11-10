# OEM sensor reverse-engineering notes — GIGABYTE G6 KF

## Why the generic sensor scan is not enough

The owner's G6 KF diagnostic shows four hardware nodes and 55 CPU sensor entries. The Intel i7-13620H CPU load sensors report values, but all CPU temperature and clock readings are N/A; all CPU power sensor entries read zero. No fan sensors are exposed by LibreHardwareMonitor. In contrast, the NVIDIA and Intel GPU nodes return valid sensor values.

The OEM Control Center screenshots supplied by the owner show CPU temperature 60 °C, CPU clock 2089 MHz, CPU utilization 7%, CPU fan 3541 RPM / 47%, and GPU fan 2260 RPM / 28%. These observations prove that the OEM application has access to a telemetry path not currently exposed by the generic WMI/LHM scan. The screenshots do not by themselves identify the transport or API.

## Static evidence from the owner's CC40.exe

The uploaded CC40.exe was inspected as a PE/.NET binary. Its embedded string tables contain InsydeDCHU.dll, GetCurrentCpuSpeed.dll, GetProductdll.dll, NVGPU_DLL.dll, GetDCHU_Data_Integer, GetDCHU_Data_Buffer, SetDCHU_Data, SetDCHU_DataEx, ReadAppSettings, and WriteAppSettings. The same binary contains UI resource identifiers T_CPUFan_RPM_value, T_GPUFan_RPM_value, T_cpu_temp_value, and CPU_Clock_Value.

The uploaded package inventory places GetCurrentCpuSpeed.dll, InsydeDCHU.dll, GetProductdll.dll, and NVGPU_DLL.dll beside CC40.exe under FnKey/CC40. A second InsydeDCHU.dll exists in FnKey/DCHU. The user's service inventory shows DCHUService.exe running as Control Center Hotkey Service from the DriverStore.

This is strong evidence of a vendor-specific sensor path. It does not prove which specific export or method supplies each UI value. GetCurrentCpuSpeed.dll is a promising CPU-clock lead, but its exports and calling convention still need direct inspection.

## External interoperability research — candidate only

A separate public Clevo reverse-engineering report for another Clevo notebook documents a Windows stack containing DCHUService.exe, InsydeDCHU.dll, and AcpiBridge.sys. It identifies a root/WMI class named CLEVO_GET, a candidate instance name ACPI/PNP0C14/0_0, and read-oriented fan getters such as GetFANCount, GetFanStatus, Fan1Info, Fan2Info, GetFan12RPM, and GetFan34RPM. The report distinguishes these from setter methods including SetFanDuty and SetFanAutoDuty.

The same report describes an InsydeDCHU.dll fan telemetry package query (package 12) and a returned buffer with CPU/GPU RPM and temperature fields. Crucially, its authors note that this apparent read query still writes EC command/data registers as part of the ACPI read transaction. It is therefore not equivalent to passive sensor polling.

Compatibility warning: those details came from a different Clevo model and firmware. They are investigative leads only. The G6 KF's actual WMI classes, methods, DLL versions, driver ID and buffer semantics must be verified before any method is invoked or any data is interpreted.

Reference: https://github.com/samoylenkodmitry/clevo-thermald/blob/main/docs/REVERSE-ENGINEERING.md

## Safety boundaries

- Do not call setter methods such as SetFanDuty or SetFanAutoDuty.
- Do not test fan-curve writes or power-mode changes.
- Do not issue raw DeviceIoControl/IOCTL values or arbitrary ACPI/EC writes.
- Do not call the package-12 _DSM telemetry path until its side effects are understood and the owner explicitly approves that probe.
- First confirm the exact G6 KF device ID, available WMI classes and method signatures, loaded module paths, and hashes/exports of the locally installed vendor DLLs.
- Keep the user's OEM DLLs and driver binaries out of the public source repository.

## Next step

Collect the exact G6 KF WMI classes/methods, ACPI PnP IDs, DCHU service/process modules and candidate vendor DLL metadata. This repository will not invoke WMI methods or perform hardware writes until the exact machine-specific interface is verified.