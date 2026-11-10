# OEM sensor reverse-engineering notes — GIGABYTE G6 KF

## Exact inventory received from the G6 KF (2026-11-11)

- AppX package: CLEVOCO.FnhotkeysandOSD 7.101.0.0.
- Services: CCDCHUService (DCHUService.exe) and HKClipSvc are both Running / Automatic.
- ACPI bridge devices: ACPI\\CLV0001\\1 and ACPI\\CLV0002\\1, both Status OK.
- The first collector's process list did not include CC40.exe; only DCHUService.exe and HKClipSvc.exe appeared. Its loaded-module inventory was therefore empty and did not reveal which DLLs CC40 loaded.
- No CLEVO/DCHU-named classes were found in the initial root\\WMI CIM class enumeration. The explicit root\\WMI CLEVO_GET class lookup returned Not found. No WMI methods were invoked.
- The separate ACPI\\PNP0C14 WMI mapper device was not included in the first collector's filter. The v2 collector now inventories PNP0C14 and its properties before deciding whether CLEVO_GET is absent on this G6 KF.

## Local binary identity matters

The user's inventory reports two different InsydeDCHU.dll files:

- FnKey\\CC40\\InsydeDCHU.dll: 2,492,416 bytes, SHA256 DAB807B5D4A621893EF5C5C1941E9D8CE91DDA6B2518E931F4BB4727DFD80E98, Authenticode NotSigned.
- FnKey\\DCHU\\InsydeDCHU.dll: 2,503,032 bytes, SHA256 D385DEF14C5AA6CBB8EB60FD34D0EFEB92EAF39E875AB28DE05FE0FDAA7CAB9C, Authenticode Valid, signed by CLEVO CO.
- The legacy Program Files (x86)\\ControlCenter\\DCHU copy matches the latter DCHU hash.
- FnKey\\CC40\\GetCurrentCpuSpeed.dll is 18,432 bytes, SHA256 C0273E8D9578C80CB6F44CBC95CA2444A6572D985A97A89053547282D4B80095, and has no version metadata or Authenticode signature.
- DCHUService.exe is 74,256 bytes, version 6.0.46.0, SHA256 203B7CBD45635061932A032420656FF98036A5D97D5A3B44C9565D5957EF5CB0; signature status Valid with Microsoft Windows Hardware Compatibility Publisher.
- Do not substitute one InsydeDCHU.dll copy for another solely because both are version 1.0.0.1. Static exports and behavior must be checked against each exact hash.

## Static evidence from the owner's CC40.exe

Embedded strings include InsydeDCHU.dll, GetCurrentCpuSpeed.dll, GetProductdll.dll, NVGPU_DLL.dll, GetDCHU_Data_Integer, GetDCHU_Data_Buffer, SetDCHU_Data, SetDCHU_DataEx, and UI resource identifiers for CPU/GPU fan RPM, CPU temperature and CPU clock.

This is strong evidence of a vendor-specific sensor path but does not prove which export or method supplies each value.

## External interoperability research — different Clevo model, candidate only

A separate public Clevo NH5xAx reverse-engineering report documents a DCHUService WMI interface under root\\WMI using class CLEVO_GET with an instance named ACPI\\PNP0C14\\0_0. It lists getter command mappings including GetFANCount (56), GetFanStatus (97), Fan1Info (99), Fan2Info (100), GetFan12RPM (112), and GetFan34RPM (113). It lists SetFanDuty (104) and SetFanAutoDuty (105) as setters.

The same report documents an InsydeDCHU.dll / AcpiBridge.sys route using a private device-interface GUID and DeviceIoControl. Its package-12 fan telemetry operation is not a passive register read: the documented ACPI path performs an EC transaction. This is not approved for blind invocation.

Reference: https://github.com/samoylenkodmitry/clevo-thermald/blob/main/docs/REVERSE-ENGINEERING.md

Compatibility warning: these are findings for another Clevo model and firmware. They are not assumed compatible with the G6 KF.

## Safety boundaries

- Do not call any WMI setter such as SetFanDuty or SetFanAutoDuty.
- Do not call InsydeDCHU.dll functions or send DeviceIoControl until their exact signatures, argument layouts, side effects and binary hash are verified.
- Do not invoke ACPI _DSM package 12 just because it is labelled as a getter; the external report documents EC command/data side effects.
- Do not issue raw EC/SMBus/IOCTL writes, fan duty changes or power profile changes during the discovery phase.
- Keep all vendor DLLs and drivers local; do not commit proprietary binaries to the public GitHub repository.

## Next step implemented

tools/Collect-ClevoEvidence.ps1 v2 queries CLV0001, CLV0002 and PNP0C14 device properties; enumerates root\\WMI class names and relevant method metadata; checks CLEVO_GET existence without invoking methods; records service and loaded process modules; resolves driver INF paths; copies selected local vendor binaries and driver files into an evidence ZIP. Run while the OEM Control Center UI is open to capture CC40.exe's loaded modules.