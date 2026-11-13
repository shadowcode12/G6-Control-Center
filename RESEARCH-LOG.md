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


## AcpiBridge IOCTL branch-to-helper mapping (2026-11-13)

- User supplied raw bytes around file offsets 0x4B10–0x4BC0. Relative CALL targets were resolved using x64 rel32 arithmetic:
  - IOCTL 0x322400 takes JZ at 0x4AF7 to dispatcher branch 0x4B41. CALL at 0x4B4C has next RIP 0x4B51 and displacement 0xFFFFEC0F (-0x13F1), resolving to helper file offset 0x3760.
  - IOCTL 0x322404 takes JZ at 0x4AFC to branch 0x4B34. CALL at 0x4B3A has next RIP 0x4B3F and displacement 0xFFFFEF3D (-0x10C3), resolving to helper file offset 0x3A7C.
  - IOCTL 0x322408 takes JZ at 0x4B01 to branch 0x4B22. CALL at 0x4B2D has next RIP 0x4B32 and displacement 0xFFFFEDDA (-0x1226), resolving to helper file offset 0x390C.
  - IOCTL 0x32240C takes JZ at 0x4B06 to branch 0x4B10. CALL at 0x4B1B has next RIP 0x4B20 and displacement 0xFFFFF12C (-0xED4), resolving to helper file offset 0x3C4C.
- Each branch passes R8 = pointer to stack buffer at [rsp+0x50], RDX = RDI, RCX = RSI into its helper. The two event-related handlers therefore do not obviously have identical argument setup: 0x322404 branch passes R8/RDX/RCX via the same pattern without the explicit LEA of R8, whereas 0x322408 and the other two include LEA R8,[rsp+0x50]. Confirm exact stack/register semantics from caller and helper prologues before interpreting.
- All branches rejoin at common completion code offset 0x4B51. It moves EAX to R8D, restores WDF/request context, and reaches an indirect call; likely a WDF completion path but exact API symbol/target is not identified yet.
- Default unmatched IOCTL path loads 0xC0000010 (STATUS_INVALID_DEVICE_REQUEST) into R8D before joining common completion path.
- These offsets are static analysis of the exact local AcpiBridge.sys binary with SHA256 BE879AF2EF1BEAA3AD041C30ABD103C5E9E872D23EA8442B57682BB0D06EA153. No IOCTL has been sent and no device has been opened.
- Next static check: dump helper entry ranges and map file offsets to RVAs using PAGE section raw pointer 0x3200 and virtual address 0x6000. Relevant helper file offsets: 0x3760, 0x390C, 0x3A7C, 0x3C4C. Also inspect caller setup before 0x4AD0 and common epilogue around 0x4B51–0x4B88.


## Helper RVA/VA mapping and external correlation (2026-11-13)

- Using PAGE section mapping (raw pointer 0x3200, virtual address 0x6000, image base 0x140000000), the four helper target file offsets map to:
  - IOCTL 0x322400: file offset 0x3760 -> RVA 0x6560 -> VA 0x140006560.
  - IOCTL 0x322404: file offset 0x3A7C -> RVA 0x687C -> VA 0x14000687C.
  - IOCTL 0x322408: file offset 0x390C -> RVA 0x670C -> VA 0x14000670C.
  - IOCTL 0x32240C: file offset 0x3C4C -> RVA 0x6A4C -> VA 0x140006A4C.
- Independent public report for another Clevo/Insyde AcpiBridge build states IOCTL 0x322400 routes to VA 0x140006560, then to an ACPI-evaluation constructor at VA 0x140006000: https://github.com/x-hachiroku/colorful-p15-ta24-linux-fan-controller/blob/main/FAN_CONTROL.md
- The exact match between our statically decoded 0x322400 branch target and that public report's helper VA strongly corroborates the ACPI _DSM evaluation role. Since it is a different machine/build and no helper body from the user's binary has yet been decoded, mark as strong corroboration rather than final proof.
- Next inspect byte ranges around file offsets 0x3760, 0x390C, 0x3A7C, 0x3C4C and their preceding 0x40–0x60 bytes to identify helper prologues, call targets and API patterns. No driver call or hardware operation.


## AcpiBridge helper prologues and argument patterns (2026-11-13)

- User supplied helper-entry byte windows for exact AcpiBridge.sys:
  - 0x3760 (IOCTL 0x322400): x64 prologue saves RBX/RSI/RBP/RDI/R12/R13/R14; establishes RBX=RCX, RDI=RDX, RSI=R8, initializes R14D=0. Uses device/context state checks and makes a call to an internal helper.
  - 0x3A7C (IOCTL 0x322404): prologue establishes RBX=RCX, RSI=RDX; only two explicit arguments are copied into nonvolatile registers. Then performs global/device-context checks and an internal call. This signature is consistent with a wait-event registration handler that can retrieve its input buffer from the framework request, but the precise meaning remains unconfirmed until the body is decoded.
  - 0x390C (IOCTL 0x322408): prologue establishes RSI=RCX, RBX=RDX, RDI=R8; checks context/global state then performs an internal call.
  - 0x3C4C (IOCTL 0x32240C): prologue establishes RDI=RCX, RBX=RDX, R14=R8 and initializes R15D=0; checks context/global state then performs an internal call.
- These function-entry patterns support the already mapped dispatch table and confirm that the 0x322404 branch supplies only two explicit arguments, while the other three supply a third pointer argument from the dispatch stack buffer.
- Public related-project corroboration: HaseeCtl's AcpiBridge implementation names 0x322404 as IoctlWaitEvent and 0x322408 as IoctlGetNotifyValue, and its source documents 0x322400 as ACPI/WMI method evaluation and 0x32240C as app-store access. This is a separate Clevo implementation; it is useful corroboration, not a substitute for decoding the local helper bodies: https://github.com/SSRYLJRSS/HaseeCtl/blob/main/src/HaseeCtl.Core/Hw/AcpiBridge.cs and https://github.com/SSRYLJRSS/HaseeCtl/blob/main/docs/history/report_B_%E7%A1%AC%E4%BB%B6%E4%B8%8E%E5%8D%8F%E8%AE%AE%E9%AA%8C%E8%AF%81.md
- Existing local imports ObReferenceObjectByHandle, ExEventObjectType, ObfDereferenceObject and KeSetEvent are consistent with the driver maintaining a referenced event object and signalling it. This makes the wait-event interpretation plausible, but exact call sites have not yet been mapped to those imports.
- The shown helper excerpts are only partial (first 0x70-ish bytes), so no final claims are made about buffer lengths, pointer validation, WMI registration GUIDs, event ownership, app-store format or request completion semantics.
- Next static step: extend the byte dump through the remainder of each helper:
  - 0x3760 helper continuation: file offsets 0x37D0–0x390B
  - 0x390C helper continuation: 0x397C–0x3A7B
  - 0x3A7C helper continuation: 0x3AEC–0x3C4B
  - 0x3C4C helper continuation: 0x3CBC–0x3D5B (adjust upward if this function has not returned yet)
- All analysis remains static; no device handle has been opened and no IOCTL/WMI/ACPI/EC request has been made.

## AcpiBridge handler body analysis (2026-11-13)

User-provided byte ranges now extend the four helper bodies. WDF function table offsets were cross-checked against a public WDF table mapping (0x868 = WdfRequestRetrieveInputBuffer; 0x870 = WdfRequestRetrieveOutputBuffer) and Microsoft's documented buffer-retrieval APIs. The WDF APIs validate a caller-specified minimum length and return the request's input/output buffer pointer and optionally its length.

### IOCTL 0x322400 / helper VA 0x140006560
- The helper invokes WdfRequestRetrieveOutputBuffer with minimum length 0x14 (20 bytes) through WDF table slot +0x870.
- It invokes WdfRequestRetrieveInputBuffer with minimum length 0x420 (1056 bytes) through slot +0x868.
- It then calls an internal helper at approximately file offset 0x3201 (PAGE VA approximately 0x140006001), and processes returned buffer/length fields.
- This is consistent with the ACPI _DSM evaluation handler documented by independent Clevo reverse engineering, but the local 0x3201 target and caller's exact IOCTL buffer directions still need direct inspection.
- Important discrepancy: earlier static notes from the supplied InsydeDCHU.dll recorded DeviceIoControl lengths as input 0x40C and output 0x420. That would not satisfy this driver's statically observed minimum input length 0x420. Re-check the actual DLL call argument order/lengths against the DeviceIoControl prototype before treating those earlier length labels as confirmed; the helper requirements take precedence until reconciled.

### IOCTL 0x322408 / helper VA 0x14000670C
- The helper uses WDF slot +0x870 (WdfRequestRetrieveOutputBuffer) with minimum output length 4.
- On its successful path it reads a 32-bit value from the device context at offset +0x1078, stores it to the retrieved output buffer, and writes 4 to the caller-supplied bytes-returned location.
- This strongly supports the notification-value retrieval interpretation. It does not itself show that the value is CPU/GPU temperature or fan telemetry; likely it is an event/notification value (e.g., hotkey code) based on the companion wait-event path.

### IOCTL 0x322404 / helper VA 0x14000687C
- The helper uses WDF slot +0x868 (WdfRequestRetrieveInputBuffer) with minimum input length 8, consistent with receiving a pointer-sized user event HANDLE.
- Device context fields at offsets +0x107C and +0x1080 are used as a registration flag and stored event-object pointer. If a previous event was registered, its referenced object is cleared/released before replacement.
- It calls the event-object reference path using imported ObReferenceObjectByHandle and ExEventObjectType, with desired access 0x00100002 (SYNCHRONIZE | EVENT_MODIFY_STATE), then stores the referenced event object and sets the registration flag on success.
- This is strong static evidence that 0x322404 registers/replaces an event object for driver notification. KeSetEvent is imported by this driver and is consistent with a separate signalling path, but its exact caller has not yet been mapped.

### IOCTL 0x32240C / helper VA 0x140006A4C
- The partial body uses WDF slot +0x870 (output buffer) with minimum length 4 and slot +0x868 (input buffer) with minimum length 12. This is consistent with the app-settings storage protocol seen in other Clevo implementations, but the remainder of this helper must be inspected before declaring its read/write semantics or supported buffer sizes.
- The initial excerpt stopped at 0x3D5B. Subsequent user dumps completed the function through its return at approximately 0x3FF5; see the later App Store operation-branch analysis for read/write inference.

### WDF evidence sources
- Public WDF API table mapping identifies +0x868 as WdfRequestRetrieveInputBuffer and +0x870 as WdfRequestRetrieveOutputBuffer: https://github.com/TakahiroHaruyama/VDR/blob/main/ida_ioctl_propagate.py
- Microsoft documents minimum-length validation and returned buffer semantics for WdfRequestRetrieveInputBuffer and WdfRequestRetrieveOutputBuffer: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdfrequest/nf-wdfrequest-wdfrequestretrieveinputbuffer and https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdfrequest/nf-wdfrequest-wdfrequestretrieveoutputbuffer
- No device handle has been opened and no IOCTL, WMI method, ACPI _DSM or EC request has been sent.


## Correction and refinement after full AcpiBridge helper snippets (2026-11-13)

- Re-reading the exact 0x322400 helper sequence confirms the function retrieves an output buffer with minimum length 0x14 and an input buffer with minimum length 0x420. The input-buffer retrieval is performed through the WDF function table slot previously identified as WdfRequestRetrieveInputBuffer; output retrieval uses WdfRequestRetrieveOutputBuffer.
- The earlier notes that labelled the OEM DLL DeviceIoControl lengths as input 0x40C / output 0x420 are likely transposed. A public implementation of the same Insyde/Clevo protocol defines EvalInputSize=0x420 and EvalOutputSize=0x40C; this also agrees with the local driver's minimum input length. Source: https://github.com/SSRYLJRSS/HaseeCtl/blob/main/src/HaseeCtl.Core/Hw/AcpiBridge.cs
- Treat the corrected direction (input 0x420, output 0x40C) as the best-supported protocol shape, while retaining a note that the original exact DLL DeviceIoControl call argument order should be re-checked directly before declaring it definitively verified. Older uploaded binary attachments are no longer available in this conversation runtime; a re-upload or a local disassembly excerpt from the original DLL would be needed for that final cross-check.
- The 0x322400 helper calls an internal routine at file offset approximately 0x3201, which begins a larger ACPI/WMI evaluation implementation. The supplied bytes show it uses shared device/global state, passes method-related fields and lengths into internal/WDF routines, and then returns through a status/response parsing path. The inner routine still needs further bytes before its exact ACPI argument construction and error paths can be fully mapped.
- The 0x32240C app-store helper first retrieves an output buffer with minimum length 4 and input buffer with minimum length 12. It then branches based on the input flags/state and issues further internal calls. The supplied excerpt is incomplete at 0x3E80, so actual operation codes, read/write semantics and data bounds are not yet established.
- Next static dump: AcpiBridge.sys file offsets 0x32A0-0x3760 (continuation of the internal 0x322400 ACPI/WMI evaluation helper) and 0x3E80-0x4050 (continuation of the 0x32240C app-store handler). Do not send any DeviceIoControl or firmware request.


## Extended 0x322400 internal helper and 0x32240C app-store handler (2026-11-13)

- The user extended the 0x322400 handler's internal helper dump only through file offset 0x32A0; the visible bytes show the helper continuing through shared/global state and an indirect function-table call. This range is too short to identify the full ACPI argument construction or WMI call semantics. Continue from 0x32A1 through the caller/helper return boundary, ideally in 0x100-byte increments.
- The 0x32240C handler continuation shows a minimum 4-byte output buffer and 12-byte input buffer, then a conditional path and references to request/context vtable entries at offsets including +0x3B8, +0x758 and +0x738. At 0x3DB0 it sets a working length to 0x1000; at 0x3E60 it sets a state byte and begins branching on a 32-bit value from the retrieved input buffer. The supplied bytes stop at 0x3E80 before the operation branches complete. Do not yet label the operation values as read/write without the remaining branch bodies.
- Next static dump should cover 0x32A0–0x3760 (or chunks 0x32A0–0x3400, 0x3400–0x3600, 0x3600–0x3760), plus 0x3E80–0x4050 for the rest of the app-store helper.
- Re-checked GitHub Actions: run 43468867205 for commit 212800a44ca7f7639a6e6284a885231895f33922 completed with conclusion success.
- No device open, IOCTL, WMI method, ACPI _DSM request or EC access has been performed.


## ACPI complex-input construction and App Store operation decoding (2026-11-13)

### 0x322400: standard ACPI complex method input structure

- In the internal helper bytes at file offset 0x33B9, the driver writes immediate bytes 41 65 69 43, i.e. little-endian DWORD 0x43696541. Windows SDK defines ACPI_EVAL_INPUT_BUFFER_COMPLEX_SIGNATURE as the multi-character constant 'CieA'; this is an exact match.
- This is strong confirmation that the internal routine builds a standard ACPI_EVAL_INPUT_BUFFER_COMPLEX structure, not merely a proprietary lookalike. Microsoft documents this structure as Signature, MethodName/MethodNameAsUlong, Size, ArgumentCount, followed by a variable-length array of ACPI_METHOD_ARGUMENT objects (up to seven top-level arguments).
- At file offset 0x33D1, the code copies a DWORD from the supplied method request at [rsi+0x14] into the structure's MethodNameAsUlong field at offset +4. This aligns with the caller-provided method selector, expected to encode _DSM in the already-observed Insyde DLL request.
- At offset 0x343F, the local ACPI_METHOD_ARGUMENT at buffer offset +0x10 begins with DWORD 0x00100002: Type=2 (ACPI_METHOD_ARGUMENT_BUFFER), DataLength=16. This is consistent with the first _DSM argument being a 16-byte UUID buffer. The following bytes are populated by a copy helper from the caller-supplied input.
- The code then writes further argument headers/data using input fields at [rsi+0x10], [rsi+0x18], [rsi+0x1C] and [rsi+0x1E]. These are consistent with subsequent _DSM revision, function index, and package/buffer argument data, but the full nested package argument layout and argument count have not yet been completely verified.
- Internal helper also contains request-size and argument-length validation and builds a variable-size ACPI input buffer. Its full remaining body from 0x3500 through 0x3760 is still needed to map the final argument packing, ACPI send call, output conversion and error paths.
- Microsoft's ACPI docs define ACPI_EVAL_INPUT_BUFFER_COMPLEX and its fields: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/acpiioct/ns-acpiioct-_acpi_eval_input_buffer_complex_v1. The Windows SDK header uses the exact 'CieA' signature constant: https://github.com/tpn/winsdk-10/blob/master/Include/10.0.16299.0/shared/acpiioct.h

### 0x32240C: App Store read/write operation branches

- The handler body through file offset 0x3FF5 is now present in the supplied dumps; the code after that is a separate function, not part of the App Store handler.
- The handler uses a 0x1000-byte (4096-byte) maximum store size.
- At 0x3E65 it loads a DWORD operation selector from the request's input structure. Selector 0 branches to the read/copy-out path; selector 1 branches to the write/copy-in path. Other selector values are rejected with status constant 0xC0000030.
- The input structure uses two 16-bit fields at offsets +4 and +6, interpreted by the branch logic as transfer offset and length. The read path checks requested offset/length against the store boundary and available output size, and clamps the transfer length to the remaining store bytes when necessary. The write path validates offset+length against 0x1000 and checks that the input buffer includes its 8-byte header plus the requested payload.
- The write path copies data following the 8-byte request header into the backing settings store; the read path copies from the backing store into the output buffer and records a byte count/result. Exact backing-store object's lifecycle and the precise internal vtable methods still need cross-referencing, but the read/write operation distinction and bounds are strongly supported by the control flow.
- The driver-side WDF minimums remain input length >=12 and output length >=4. This is a generic IOCTL wrapper for a 4 KiB app-settings store; it is separate from ACPI _DSM command IOCTL 0x322400.
- No DeviceIoControl, WMI, ACPI _DSM or EC request has been performed.

### Next static step

- Dump the remaining 0x322400 inner helper bytes at offsets 0x3500–0x3760, ideally 0x3500–0x3600 and 0x3600–0x3760.
- No additional App Store helper bytes are needed to establish its two operation branches; only deeper cross-reference of the backing-store context is optional.


## ACPI complex signature and app-settings ABI cross-check (2026-11-13)

- The 0x322400 internal helper writes the exact ACPI_EVAL_INPUT_BUFFER_COMPLEX_SIGNATURE. In file bytes this is 41 65 69 43; the Windows SDK macro is 'CieA' and evaluates to DWORD 0x43696541. This confirms use of the standard Windows ACPI complex-input structure.
- The standard structure has Signature, MethodName/MethodNameAsUlong, Size, ArgumentCount, and a variable-length ACPI_METHOD_ARGUMENT array. Microsoft documents this field order and the use of the structure for IOCTL_ACPI_EVAL_METHOD.
- The first ACPI_METHOD_ARGUMENT is concretely built with Type=2 (BUFFER) and DataLength=16, supporting a 16-byte _DSM UUID argument. The supplied method selector and subsequent 32-bit values/length fields are copied from the Insyde request. The final nested package/buffer argument and argument count still require the remainder of the helper body to be disassembled.
- App Store operation layout has an independent source-code cross-check in HaseeCtl's AcpiBridge implementation:
  - Read uses a 12-byte input header, DWORD op=0 and DWORD at offset 4 equal to 0x10000000. As two little-endian 16-bit fields this is offset=0, length=0x1000; output buffer size is 0x1000.
  - Write uses DWORD op=1, USHORT offset at +4, USHORT data length at +6, then payload at +8.
  - The local driver's exact 0x32240C branch logic checks op 0/1, enforces the 0x1000 boundary, validates input payload length for writes, and validates/clamps read length to the store/output bounds.
  - This source-level cross-check supports the local inference that 0=read, 1=write, +4=offset, +6=length, and payload starts at +8. The backing store is 4096 bytes.
  - Reference implementation: https://github.com/SSRYLJRSS/HaseeCtl/blob/676161faeef390967d0a824ff0c6b060a15e74a2/src/HaseeCtl.Core/Hw/AcpiBridge.cs and its hardware report: https://github.com/SSRYLJRSS/HaseeCtl/blob/676161faeef390967d0a824ff0c6b060a15e74a2/docs/history/report_B_%E7%A1%AC%E4%BB%B6%E4%B8%8E%E5%8D%8F%E8%AE%AE%E9%AA%8C%E8%AF%81.md
- This app-settings mechanism is not a sensor telemetry API. It holds application settings, including possible Control Center preferences, and should not be used as a CPU temperature/fan RPM reader.
- Next static task remains 0x322400 inner helper bytes 0x3500–0x3760; the App Store handler is complete enough for its operation format and bounds.


## Completion of local ACPI _DSM transport path (2026-11-13)

### Exact transition from private bridge IOCTL to Windows ACPI evaluation

- The user's supplied bytes show instruction at file offset 0x3587: \`41 B9 04 C0 32 00\`, loading R9D with control code 0x0032C004.
- 0x0032C004 is the Windows \`IOCTL_ACPI_EVAL_METHOD\` value (FILE_DEVICE_ACPI, function 1, METHOD_BUFFERED, read/write access), not the vendor-private user-mode \`0x322400\` code.
- Therefore the data path is now statically established as: user-mode private IOCTL 0x322400 -> AcpiBridge.sys -> construct ACPI_EVAL_INPUT_BUFFER_COMPLEX -> synchronously send IOCTL_ACPI_EVAL_METHOD (0x0032C004) to the ACPI I/O target -> validate and parse ACPI_EVAL_OUTPUT_BUFFER.
- Microsoft documents IOCTL_ACPI_EVAL_METHOD as a synchronous request for an ACPI control method and documents ACPI_EVAL_INPUT_BUFFER_COMPLEX as the input structure containing method name and ACPI_METHOD_ARGUMENT array: https://learn.microsoft.com/en-us/windows-hardware/drivers/acpi/evaluating-acpi-control-methods-synchronously and https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/acpiioct/ns-acpiioct-_acpi_eval_input_buffer_complex_v1. The numeric IOCTL value is also defined as 0x0032C004 in the acpiioct.h-derived reference: https://ntdoc.m417z.com/ioctl_acpi_eval_method
- At file offset 0x3679, the helper compares the returned output buffer's first DWORD with 0x426F6541. In little-endian memory the signature bytes are \`41 65 6F 42\` ("AeoB"), matching \`ACPI_EVAL_OUTPUT_BUFFER_SIGNATURE\` ('BoeA'). This is a concrete signature validation before response parsing. Microsoft describes the ACPI_EVAL_OUTPUT_BUFFER header as Signature, Length, Count, followed by ACPI_METHOD_ARGUMENT entries: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/acpiioct/ns-acpiioct-_acpi_eval_output_buffer_v1
- The internal ACPI input structure writes \`ACPI_EVAL_INPUT_BUFFER_COMPLEX_SIGNATURE\` bytes \`41 65 69 43\` at file offset 0x33B9 (DWORD 0x43696541, macro 'CieA'). This offset supersedes the earlier tentative 0x33BA note.
- It sets ArgumentCount=4 and places the supplied method name in MethodNameAsUlong. The observed method-name input is \`_DSM\`.
- The four ACPI method arguments constructed by the helper are:
  1. Type BUFFER (2), DataLength 16: the 16-byte DCHU _DSM UUID.
  2. Type INTEGER (0), DataLength 4: the caller-supplied revision value from the request.
  3. Type INTEGER (0), DataLength 4: the caller-supplied _DSM function/command index.
  4. Type PACKAGE_EX (4): DataLength copied from the request; its contents include the nested ACPI_METHOD_ARGUMENT descriptor and data buffer passed to the _DSM.
- The request's nested payload header is consistent with \`Type=BUFFER (2), DataLength=0x100 (256)\`, encoded as DWORD 0x01000002, followed by the 256-byte payload. The enclosing package argument length is 0x104 (260) bytes in the common full-size request. The computed ACPI argument-array Size is this package length plus the fixed preceding/header overhead (0x28), for 0x12C bytes when the package payload is 0x104.
- Standard ACPI_METHOD_ARGUMENT Type values are confirmed by acpiioct.h: INTEGER=0, STRING=1, BUFFER=2, PACKAGE=3, PACKAGE_EX=4. Microsoft documentation describes the argument types and DataLength field: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/acpiioct/ns-acpiioct-_acpi_method_argument_v1 and Windows SDK-derived header: https://github.com/tpn/winsdk-10/blob/master/Include/10.0.16299.0/shared/acpiioct.h
- The helper creates a standard Windows ACPI method argument tree; it does not directly issue raw EC port/register accesses from user mode. Firmware/AML may perform embedded-controller operations after ACPI evaluates the requested _DSM function.

### Remaining uncertainty: outer private IOCTL buffer directions

- Keep outer DeviceIoControl input/output size labels provisional. The internal ACPI evaluator's own ACPI_EVAL_INPUT_BUFFER_COMPLEX / ACPI_EVAL_OUTPUT_BUFFER sizes must not be conflated with the outer private IOCTL 0x322400's WDF request input/output sizes.
- The user's provided dispatch/helper excerpts omit file offsets 0x37D0–0x38EB from the outer 0x322400 wrapper function. Inspect that gap to confirm the local wrapper's exact WdfRequestRetrieveInputBuffer/WdfRequestRetrieveOutputBuffer calls and minimum lengths.
- An independent same-family implementation uses outer DeviceIoControl input 0x420/output 0x40C, but exact directions in this G6 KF binary remain pending until the omitted wrapper body is examined.

### Next static step

- Dump file offsets 0x37D0–0x390B (outer private IOCTL 0x322400 handler continuation). No more bytes from the 0x3200–0x375F ACPI evaluator are needed to establish the underlying IOCTL_ACPI_EVAL_METHOD path and four _DSM argument types.
- No device handle was opened and no IOCTL/WMI/ACPI/EC request was performed.
