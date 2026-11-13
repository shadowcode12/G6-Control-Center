[CmdletBinding()]
param([string]$Path = "$env:windir\System32\drivers\AcpiBridge.sys")

$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $Path).Path
$script:Bytes = [IO.File]::ReadAllBytes($resolved)

function U16([int]$o) { [BitConverter]::ToUInt16($script:Bytes, $o) }
function U32([int]$o) { [BitConverter]::ToUInt32($script:Bytes, $o) }
function U64([int]$o) { [BitConverter]::ToUInt64($script:Bytes, $o) }
function AsciiZ([int]$o) {
    if ($o -lt 0 -or $o -ge $script:Bytes.Length) { return '' }
    $e = $o
    while ($e -lt $script:Bytes.Length -and $script:Bytes[$e] -ne 0) { $e++ }
    [Text.Encoding]::ASCII.GetString($script:Bytes, $o, $e - $o)
}

if ($script:Bytes.Length -lt 256 -or $script:Bytes[0] -ne 0x4D -or $script:Bytes[1] -ne 0x5A) {
    throw 'Not a valid MZ/PE file.'
}
$pe = [int](U32 0x3C)
if ($script:Bytes[$pe] -ne 0x50 -or $script:Bytes[$pe + 1] -ne 0x45 -or $script:Bytes[$pe + 2] -ne 0 -or $script:Bytes[$pe + 3] -ne 0) {
    throw 'PE signature not found.'
}

$coff = $pe + 4
$machine = U16 $coff
$sectionsCount = U16 ($coff + 2)
$optionalSize = U16 ($coff + 16)
$opt = $coff + 20
$magic = U16 $opt
if ($magic -eq 0x20B) {
    $arch = 'PE32+ x64'
    $dir = 112
    $is64 = $true
    $imageBase = U64 ($opt + 24)
} elseif ($magic -eq 0x10B) {
    $arch = 'PE32 x86'
    $dir = 96
    $is64 = $false
    $imageBase = U32 ($opt + 28)
} else { throw ('Unknown PE optional header: 0x{0:X}' -f $magic) }

$sizeHeaders = U32 ($opt + 60)
$exportRva = U32 ($opt + $dir)
$importRva = U32 ($opt + $dir + 8)
$script:Sections = @()
$sectionTable = $opt + $optionalSize
for ($i = 0; $i -lt $sectionsCount; $i++) {
    $o = $sectionTable + (40 * $i)
    $script:Sections += [pscustomobject]@{
        Name = [Text.Encoding]::ASCII.GetString($script:Bytes, $o, 8).Trim([char]0)
        VirtualSize = U32 ($o + 8)
        VirtualAddress = U32 ($o + 12)
        RawSize = U32 ($o + 16)
        RawPointer = U32 ($o + 20)
    }
}

function RvaOffset([uint32]$rva) {
    foreach ($s in $script:Sections) {
        $span = [Math]::Max([double]$s.VirtualSize, [double]$s.RawSize)
        if ($rva -ge $s.VirtualAddress -and [double]$rva -lt ([double]$s.VirtualAddress + $span)) {
            $delta = [double]$rva - [double]$s.VirtualAddress
            if ($delta -ge $s.RawSize) { return -1 }
            return [int]($s.RawPointer + $delta)
        }
    }
    if ($rva -lt $sizeHeaders) { return [int]$rva }
    return -1
}

Write-Output '=== Driver identity ==='
[pscustomobject]@{
    Path = $resolved
    SizeBytes = $script:Bytes.Length
    SHA256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
    FileVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($resolved).FileVersion
    ProductVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($resolved).ProductVersion
    SignatureStatus = (Get-AuthenticodeSignature -LiteralPath $resolved).Status
    Signer = (Get-AuthenticodeSignature -LiteralPath $resolved).SignerCertificate.Subject
} | Format-List | Out-String | Write-Output

Write-Output '=== PE header ==='
[pscustomobject]@{
    Architecture = $arch
    Machine = ('0x{0:X4}' -f $machine)
    ImageBase = ('0x{0:X}' -f $imageBase)
    SectionCount = $sectionsCount
    ExportRVA = ('0x{0:X}' -f $exportRva)
    ImportRVA = ('0x{0:X}' -f $importRva)
} | Format-List | Out-String | Write-Output

Write-Output '=== Sections ==='
$script:Sections | Format-Table -AutoSize | Out-String | Write-Output

Write-Output '=== Imported modules and functions ==='
if ($importRva -ne 0) {
    $imp = RvaOffset $importRva
    if ($imp -lt 0) { throw 'Cannot map import directory RVA.' }
    for ($d = 0; $d -lt 128; $d++) {
        $o = $imp + (20 * $d)
        $oft = U32 $o
        $nameRva = U32 ($o + 12)
        $ft = U32 ($o + 16)
        if (($oft -bor $nameRva -bor $ft) -eq 0) { break }
        $nameOffset = RvaOffset $nameRva
        if ($nameOffset -lt 0) { continue }
        Write-Output ('[{0}]' -f (AsciiZ $nameOffset))
        $lookup = if ($oft -ne 0) { $oft } else { $ft }
        $thunk = RvaOffset $lookup
        if ($thunk -lt 0) { continue }
        for ($t = 0; $t -lt 2048; $t++) {
            if ($is64) {
                $v = U64 ($thunk + (8 * $t))
                if ($v -eq 0) { break }
                if ($v -ge [UInt64]::Parse('9223372036854775808')) {
                    Write-Output ('  Ordinal #{0}' -f ($v % 65536))
                } else {
                    $hn = RvaOffset ([uint32]$v)
                    if ($hn -ge 0) { Write-Output ('  {0}' -f (AsciiZ ($hn + 2))) }
                }
            } else {
                $v = U32 ($thunk + (4 * $t))
                if ($v -eq 0) { break }
                if ($v -ge 0x80000000) {
                    Write-Output ('  Ordinal #{0}' -f ($v % 65536))
                } else {
                    $hn = RvaOffset $v
                    if ($hn -ge 0) { Write-Output ('  {0}' -f (AsciiZ ($hn + 2))) }
                }
            }
        }
    }
} else { Write-Output '(No normal import table)' }

Write-Output '=== Embedded strings of interest ==='
$pattern = '(?i)(acpi|dchu|deviceiocontrol|createdevice|ioctl|wdf|wmi|firmware|bios|insyde|clevo|clv0001|clv0002|fan|temp|thermal|\\\\device|irp_mj|controlcode|ec)'
$found = 0
$i = 0
while ($i -lt $script:Bytes.Length -and $found -lt 200) {
    if ($script:Bytes[$i] -ge 0x20 -and $script:Bytes[$i] -le 0x7E) {
        $start = $i
        while ($i -lt $script:Bytes.Length -and $script:Bytes[$i] -ge 0x20 -and $script:Bytes[$i] -le 0x7E) { $i++ }
        $len = $i - $start
        if ($len -ge 5) {
            $s = [Text.Encoding]::ASCII.GetString($script:Bytes, $start, $len)
            if ($s -match $pattern) { Write-Output ('ASCII: ' + $s); $found++ }
        }
    } else { $i++ }
}



Write-Output '=== PE debug / CodeView metadata ==='
$debugDirEntry = $opt + $dir + (6 * 8)
$debugRva = U32 $debugDirEntry
$debugSize = U32 ($debugDirEntry + 4)
if ($debugRva -ne 0 -and $debugSize -ge 28) {
    $debugOffset = RvaOffset $debugRva
    if ($debugOffset -ge 0) {
        $debugCount = [Math]::Min([int]($debugSize / 28), 64)
        for ($n = 0; $n -lt $debugCount; $n++) {
            $d = $debugOffset + (28 * $n)
            $type = U32 ($d + 12)
            $dataSize = U32 ($d + 16)
            $rawData = U32 ($d + 24)
            if ($type -eq 2 -and $dataSize -ge 24 -and $rawData -ge 0 -and ($rawData + $dataSize) -le $script:Bytes.Length) {
                $sig = [Text.Encoding]::ASCII.GetString($script:Bytes, [int]$rawData, 4)
                if ($sig -eq 'RSDS') {
                    $guidBytes = New-Object byte[] 16
                    [Array]::Copy($script:Bytes, [int]($rawData + 4), $guidBytes, 0, 16)
                    $cvGuid = [Guid]::new($guidBytes)
                    $age = U32 ([int]($rawData + 20))
                    $pdb = AsciiZ ([int]($rawData + 24))
                    [pscustomobject]@{ Signature=$sig; Guid=$cvGuid; Age=$age; PdbPath=$pdb } | Format-List | Out-String | Write-Output
                }
            }
        }
    }
} else {
    Write-Output '(No PE debug directory advertised.)'
}

Write-Output '=== Embedded UTF-16LE strings of interest ==='
$unicodePattern = '(?i)(acpi|dchu|deviceiocontrol|ioctl|wdf|wmi|firmware|bios|insyde|clevo|clv0001|clv0002|fan|temp|thermal|\\\\device|irp_mj|controlcode|ec|\\\\.pdb)'
$unicodeCount = 0
$i = 0
while ($i -lt ($script:Bytes.Length - 1) -and $unicodeCount -lt 200) {
    if ($script:Bytes[$i] -ge 0x20 -and $script:Bytes[$i] -le 0x7E -and $script:Bytes[$i + 1] -eq 0) {
        $start = $i
        $j = $i
        while (($j + 1) -lt $script:Bytes.Length -and $script:Bytes[$j] -ge 0x20 -and $script:Bytes[$j] -le 0x7E -and $script:Bytes[$j + 1] -eq 0) { $j += 2 }
        $length = [int](($j - $start) / 2)
        if ($length -ge 5) {
            $value = [Text.Encoding]::Unicode.GetString($script:Bytes, $start, $j - $start)
            if ($value -match $unicodePattern) {
                Write-Output ('UTF16: ' + $value)
                $unicodeCount++
            }
        }
        $i = $j + 2
    } else { $i += 2 }
}

Write-Output '=== Binary fingerprints ==='
$fingerprints = [ordered]@{
    'CLV0001 device interface GUID (in-memory GUID byte order)' = [byte[]](0x74,0x4C,0x99,0x86,0x43,0xAD,0x12,0x48,0xB7,0xE7,0x0C,0x42,0x0B,0x5C,0x5F,0xD7)
    'ACPI _DSM UUID (in-memory GUID byte order)' = [byte[]](0xE4,0xF2,0x24,0x93,0xDC,0xFB,0xDC,0x4B,0xAD,0xD6,0xDB,0x71,0xBD,0xC0,0xAF,0xAD)
    'candidate IOCTL 0x322400' = [byte[]](0x00,0x24,0x32,0x00)
    'candidate IOCTL 0x322404' = [byte[]](0x04,0x24,0x32,0x00)
    'candidate IOCTL 0x322408' = [byte[]](0x08,0x24,0x32,0x00)
    'candidate IOCTL 0x32240C' = [byte[]](0x0C,0x24,0x32,0x00)
}
foreach ($item in $fingerprints.GetEnumerator()) {
    $hits = [System.Collections.Generic.List[string]]::new()
    $needle = [byte[]]$item.Value
    for ($pos = 0; $pos -le ($script:Bytes.Length - $needle.Length); $pos++) {
        $match = $true
        for ($k = 0; $k -lt $needle.Length; $k++) {
            if ($script:Bytes[$pos + $k] -ne $needle[$k]) { $match = $false; break }
        }
        if ($match) { $hits.Add(('0x{0:X}' -f $pos)) }
    }
    Write-Output ('{0}: {1}' -f $item.Key, $(if ($hits.Count) { $hits -join ', ' } else { 'not found as a contiguous byte sequence' }))
}

Write-Output ''
Write-Output 'Static file inspection only. No device handle, IOCTL, WMI method, ACPI _DSM request, or EC access is performed.'
