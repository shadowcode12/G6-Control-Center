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

## Exact CLV0001 AcpiBridge.sys static image inspection (2026-11-13)

- The user ran Inspect-DriverImage.ps1 against `C:\\Windows\\System32\\drivers\\AcpiBridge.sys`. Its SHA-256 matches the independently reported local driver metadata: BE879AF2EF1BEAA3AD041C30ABD103C5E9E872D23EA8442B57682BB0D06EA153; size 83,736 bytes; x64 PE32+ machine 0x8664; version 1.0.0.7; valid Microsoft Windows Hardware Compatibility Publisher signature.
- PE has 8 sections (.text, .rdata, .data, .pdata, PAGE, INIT, .rsrc, .reloc), no export directory and an import directory at RVA 0x81FC.
- Imports: ntoskrnl.exe (MmGetSystemRoutineAddress, ExEventObjectType, ObfDereferenceObject, IoWMIRegistrationControl, RtlCopyUnicodeString, RtlInitUnicodeString, DbgPrintEx, ObReferenceObjectByHandle, ExFreePoolWithTag, ExAllocatePoolWithTag, KeSetEvent); WppRecorder.sys (trace recorder APIs); WDFLDR.SYS (WDF version bind/unbind APIs).
- The WDF loader imports plus PAGE/INIT sections are consistent with a KMDF driver. IoWMIRegistrationControl establishes use of the kernel WMI registration API, but does not reveal which WMI blocks/instances/methods are registered or prove that root\\WMI:CLEVO_GET exists. MmGetSystemRoutineAddress indicates some kernel routines may be resolved dynamically. Absence of a normal DeviceIoControl import is expected for a kernel driver and does not disprove an IRP/IOCTL dispatch path.
- Embedded PDB path is `C:\\Emmett\\Clevo\\acpi-bridge-driver\\x64\\Release\\AcpiBridge.pdb`. This is build/debug metadata, not proof that source is public or available.
- Public Clevo NH5xAx reverse-engineering notes describe a CLV0001 AcpiBridge.sys implementation using the same interface GUID, a KMDF dispatcher and IOCTL 0x322400 ACPI _DSM path. However, the public report's AcpiBridge.sys hash is 58e24c053b87cd4a8b76565bd7f5830cd946faa5dd9e4691f9348e1453c8df96, which does not match this G6 KF binary. Its PDB path also differs. Treat its command dispatch details as family-level leads only, not as proven offsets/semantics for the user's 1.0.0.7 binary.
- Public G5 KC research independently documents the same CLV0001 interface GUID and Insyde KMDF AcpiBridge family, but that is another model/firmware. Do not copy its EC command behaviour into G6 KF without matching this machine's ACPI tables.
- No device open, IOCTL, WMI method, ACPI _DSM, or EC operation has been performed.
- Next static task: inspect the PE debug/CodeView record, scan UTF-16 strings, and locate the CLV0001 interface GUID / _DSM UUID / candidate IOCTL constants in the exact driver image. Then compare those static fingerprints against the user's exact InsydeDCHU.dll build.
- Public comparison sources: https://github.com/samoylenkodmitry/clevo-thermald/blob/main/docs/REVERSE-ENGINEERING.md and https://github.com/PabloJustDevelops/gigabyte-g5-kc-driver-keyboard/blob/main/docs/WINDOWS-RESEARCH.md


## Exact AcpiBridge 1.0.0.7 binary fingerprints (2026-11-13)

- The user's latest Inspect-DriverImage.ps1 output confirms CodeView RSDS metadata: PDB GUID 3a04dc22-8512-42e7-96aa-8840cad72988, age 1, path `C:\\Emmett\\Clevo\\acpi-bridge-driver\\x64\\Release\\AcpiBridge.pdb`. GitHub code search for this exact GUID/path did not find a public PDB/source match. Treat the PDB path as a build breadcrumb, not evidence that source code is public.
- The exact CLV0001 device-interface GUID byte sequence appears at file offset 0x2130.
- Candidate IOCTL value 0x322400 appears as little-endian bytes at file offset 0x4AF3. Given PAGE section raw pointer 0x3200 and virtual address 0x6000, this file offset maps to RVA 0x78F3 (VA 0x1400078F3 for image base 0x140000000). This is a static byte match only; surrounding instruction bytes must be examined before treating it as an active dispatch comparison.
- The ACPI _DSM UUID 93f224e4-fbdc-4bbf-add6-db71bdc0afad is not present as one contiguous in-memory GUID byte sequence in this driver image. This is consistent with the driver receiving the method GUID in the user-mode IOCTL input and forwarding/evaluating it, rather than embedding the method UUID in its own image; it does not prove that exact implementation.
- The user's actual InsydeDCHU.dll disassembly separately constructs the same _DSM UUID and submits IOCTL 0x322400, giving a strong cross-component protocol fingerprint: interface GUID/device + matching IOCTL candidate in AcpiBridge.sys + same IOCTL in the user DLL. Still static evidence, not runtime confirmation.
- Public cross-check: https://github.com/x-hachiroku/colorful-p15-ta24-linux-fan-controller/blob/main/FAN_CONTROL.md records an AcpiBridge.sys dispatch routine for 0x322400 at VA 0x1400078F1 in another Clevo/Insyde build, and its DLL path constructs the same UUID/_DSM request. This is very close in address to this binary's candidate byte match (VA 0x1400078F3), but the public report is another laptop/build and the local CodeView GUID has not matched it. Do not claim the machine code is identical without examining bytes/disassembly.
- Public cross-check: https://github.com/SSRYLJRSS/HaseeCtl/blob/main/src/HaseeCtl.Core/Hw/AcpiBridge.cs defines the same interface GUID and IOCTL 0x322400 as an ACPI/WMI method evaluation path, and additional IOCTLs 0x322404, 0x322408 and 0x32240C for event notification and app storage. This is implementation evidence from a different Clevo model/software project, not confirmed G6 KF behaviour. The local scan did not find the latter IOCTL byte sequences in AcpiBridge.sys; they may be encoded or handled differently, so do not infer absence from this scan.
- Next static check is a small hex dump around file offset 0x4AF3 (approximately 0x4AD0–0x4B20) to identify instruction boundaries and confirm whether the immediate belongs to the PAGE dispatch routine. Do not invoke DeviceIoControl or issue hardware requests for this check.


## AcpiBridge IOCTL dispatcher instruction decoding (2026-11-13)

- User supplied a read-only hex dump of the exact installed AcpiBridge.sys around file offset 0x4AD0–0x4B20.
- The candidate constant at file offset 0x4AF3 is part of the instruction beginning at 0x4AF1: bytes `81 EB 00 24 32 00`, x64 decode `sub ebx, 0x00322400`.
- Following conditional branches and arithmetic are:
  - 0x4AF7: `74 48` => JZ to file offset 0x4B41.
  - 0x4AF9: `83 EB 04` => subtract 4 from EBX; 0x4AFC `74 36` => JZ to 0x4B34.
  - 0x4AFE: `83 EB 04` => subtract 4 again; 0x4B01 `74 1F` => JZ to 0x4B22.
  - 0x4B03: `83 FB 04` => compare EBX to 4; 0x4B06 `74 08` => JZ to 0x4B10.
  - Default path at 0x4B08 loads R8D with 0xC0000010 (STATUS_INVALID_DEVICE_REQUEST) and jumps to common exit at 0x4B54.
- If EBX is the incoming IoControlCode (which must be confirmed by decoding the caller/context), this dispatch recognizes four consecutive codes: 0x322400 -> 0x4B41; 0x322404 -> 0x4B34; 0x322408 -> 0x4B22; 0x32240C -> 0x4B10. The subtraction pattern explains why a contiguous byte scan did not find literal 0x322404/408/40C constants.
- This is strong static evidence for a four-way private-control dispatch, but the snippet alone does not identify the work performed by each handler or independently prove the EBX source. No IOCTL was invoked.
- Next static task: inspect raw bytes and disassemble the four branch target ranges, especially file offsets 0x4B10, 0x4B22, 0x4B34, 0x4B41 and common/default exit around 0x4B54. Confirm the function argument/register setup leading into the EBX comparison before assigning final IOCTL semantics.
