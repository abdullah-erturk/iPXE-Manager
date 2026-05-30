import os, sys, json, shutil, subprocess, time, threading, re, ctypes, ctypes.wintypes, tempfile
import socket, atexit, traceback, stat
from urllib.parse import quote
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, session, Response, stream_with_context
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIG ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Her kuruluma özgü secret key — oturum güvenliği için rastgele üretilir ve dosyaya kaydedilir
_key_file = os.path.join(BASE_DIR, '.secret_key')
try:
    app.secret_key = open(_key_file).read().strip() if os.path.exists(_key_file) else None
    if not app.secret_key:
        app.secret_key = os.urandom(24).hex()
        with open(_key_file, 'w') as _kf: _kf.write(app.secret_key)
except Exception:
    app.secret_key = 'pxe_fallback_key'

PXE_DIR     = os.path.join(BASE_DIR, 'pxe')
ISO_DIR     = os.path.join(PXE_DIR, 'ISO')
WIM_DIR     = os.path.join(PXE_DIR, 'WINPE')
ISO_WIN_DIR = os.path.join(ISO_DIR, 'Windows')
ISO_LIN_DIR = os.path.join(ISO_DIR, 'Linux')
PXESRV_EXE  = os.path.join(PXE_DIR, 'pxesrv.exe')

for d in [ISO_DIR, WIM_DIR, PXE_DIR, ISO_WIN_DIR, ISO_LIN_DIR]:
    os.makedirs(d, exist_ok=True)

# Yüklenen dosyaların Windows'un kendi Temp'inde şişip RAM'i çökertmesini engeller.
os.environ['TMPDIR'] = PXE_DIR
tempfile.tempdir = PXE_DIR

pxe_process = None

# ─── GÖMÜLÜ (EMBEDDED) POWERSHELL BETİĞİ ────────────────────────────────────
PS_EXTRACT_SCRIPT = r"""
# Linux PXE File Extractor - iPXE Manager
# writed by Abdullah ERTÜRK - github.com/abdullah-erturk
# Supports: Ubuntu, Debian, Fedora, RHEL, Arch, Manjaro, Alpine, openSUSE, Void, Mint, Kali, MX
param([string]$IsoPath = "", [string]$PreMountedDrive = "")

if (-not $IsoPath) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $isos = Get-ChildItem -Path $scriptDir -Filter "*.iso" -File
    if ($isos.Count -eq 0) { Write-Host "[ERROR] No ISO found." -ForegroundColor Red; exit 1 }
    $IsoPath = $isos[0].FullName
}
$DestDir = Split-Path -Parent $IsoPath

function Log { param([string]$m, [string]$c = "Gray") Write-Host $m -ForegroundColor $c }

# --- Distro detection by ISO structure (not filename) ---
function Get-DistroType { param([string]$Drive)
    if (Test-Path "$Drive\casper\filesystem.squashfs") { return "ubuntu" }
    if (Test-Path "$Drive\casper\filesystem.manifest") { return "ubuntu" }
    if (Test-Path "$Drive\casper") { return "ubuntu" }
    if (Test-Path "$Drive\live\filesystem.squashfs")   { return "debian" }
    if (Test-Path "$Drive\live\filesystem.squashfs.part") { return "debian" }
    if (Test-Path "$Drive\LiveOS\squashfs.img") {
        if (Test-Path "$Drive\boot\x86_64") { return "fedora" }
        return "rhel"
    }
    if (Test-Path "$Drive\boot\x86_64\loader\linux") { return "opensuse" }
    if (Test-Path "$Drive\boot\x86_64\loader")         { return "opensuse" }
    if (Test-Path "$Drive\arch\boot\x86_64\vmlinuz-linux") { return "arch" }
    if (Test-Path "$Drive\arch")                           { return "arch" }
    if (Test-Path "$Drive\manjaro")                        { return "manjaro" }
    if (Test-Path "$Drive\alpine-release")                 { return "alpine" }
    if (Test-Path "$Drive\boot\vmlinuz-lts")              { return "alpine" }
    if (Test-Path "$Drive\boot\vmlinuz") {
        if (Test-Path "$Drive\LiveOS")                     { return "rhel" }
        return "void"
    }
    if (Test-Path "$Drive\nix-store")                      { return "nixos" }
    return "generic"
}

# --- Per-distro kernel/initrd paths ---
function Get-KernelPath { param([string]$Drive, [string]$Distro)
    $map = @{
        "ubuntu"   = @("casper\vmlinuz", "casper\vmlinuz.efi")
        "debian"   = @("live\vmlinuz", "install.amd\vmlinuz", "live\vmlinuz.efi")
        "fedora"   = @("images\pxeboot\vmlinuz", "boot\x86_64\vmlinuz")
        "rhel"     = @("images\pxeboot\vmlinuz", "boot\vmlinuz")
        "opensuse" = @("boot\x86_64\loader\linux", "boot\x86_64\linux")
        "arch"     = @("arch\boot\x86_64\vmlinuz-linux", "arch\boot\x86_64\vmlinuz")
        "manjaro"  = @("boot\vmlinuz", "manjaro\boot\x86_64\vmlinuz")
        "alpine"   = @("boot\vmlinuz-lts", "boot\vmlinuz")
        "void"     = @("boot\vmlinuz")
        "nixos"    = @("boot\bzImage")
        "generic"  = @("isolinux\vmlinuz", "syslinux\vmlinuz", "boot\vmlinuz",
                       "casper\vmlinuz", "live\vmlinuz", "images\pxeboot\vmlinuz")
    }
    $paths = $map[$Distro]
    if (-not $paths) { $paths = $map["generic"] }
    foreach ($rel in $paths) {
        $f = Join-Path $Drive $rel
        if (Test-Path $f) { return Get-Item $f }
    }
    return Get-ChildItem -Path $Drive -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^vmlinuz|^linux$|^bzImage$" } |
        Sort-Object Length -Descending | Select-Object -First 1
}

function Get-InitrdPath { param([string]$Drive, [string]$Distro)
    $map = @{
        "ubuntu"   = @("casper\initrd", "casper\initrd.lz", "casper\initrd.gz")
        "debian"   = @("live\initrd.img", "live\initrd.gz", "install.amd\initrd.gz")
        "fedora"   = @("images\pxeboot\initrd.img", "boot\x86_64\initrd")
        "rhel"     = @("images\pxeboot\initrd.img", "boot\initrd.img")
        "opensuse" = @("boot\x86_64\loader\initrd")
        "arch"     = @("arch\boot\x86_64\initramfs-linux.img", "arch\boot\x86_64\initramfs.img")
        "manjaro"  = @("boot\initramfs.img", "manjaro\boot\x86_64\initramfs.img")
        "alpine"   = @("boot\initramfs-lts", "boot\initramfs")
        "void"     = @("boot\initrd")
        "nixos"    = @("boot\initrd")
        "generic"  = @("isolinux\initrd.img", "syslinux\initrd.img", "boot\initrd.img",
                       "casper\initrd", "live\initrd.img", "images\pxeboot\initrd.img")
    }
    $paths = $map[$Distro]
    if (-not $paths) { $paths = $map["generic"] }
    foreach ($rel in $paths) {
        $f = Join-Path $Drive $rel
        if (Test-Path $f) { return Get-Item $f }
    }
    return Get-ChildItem -Path $Drive -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^initrd|^initramfs" } |
        Sort-Object Length -Descending | Select-Object -First 1
}

# --- Squashfs dosyasini bul ---
function Find-Squashfs { param([string]$Drive, [string]$Distro)
    if ($Distro -eq "ubuntu") {
        $casperDir = Join-Path $Drive "casper"
        if (Test-Path (Join-Path $casperDir "filesystem.squashfs")) {
            return Get-Item (Join-Path $casperDir "filesystem.squashfs")
        }
        $allSqfs = Get-ChildItem -Path $casperDir -Filter "*.squashfs" -File -ErrorAction SilentlyContinue
        if ($allSqfs -and $allSqfs.Count -gt 1) { return $null }
        if ($allSqfs -and $allSqfs.Count -eq 1) { return $allSqfs[0] }
        return $null
    }
    $candidates = switch ($Distro) {
        "debian"   { @("live") }
        "fedora"   { @("LiveOS","images") }
        "rhel"     { @("LiveOS","images") }
        "opensuse" { @("LiveOS") }
        "void"     { @("LiveOS") }
        "nixos"    { @("nix-store","boot") }
        "arch"     { @("arch","x86_64") }
        "manjaro"  { @("manjaro","x86_64") }
        default    { @("LiveOS","casper","live") }
    }
    foreach ($dir in $candidates) {
        $dirPath = Join-Path $Drive $dir
        if (-not (Test-Path $dirPath)) { continue }
        $f = Get-ChildItem -Path $dirPath -Filter "*.squashfs" -File -ErrorAction SilentlyContinue |
             Sort-Object Length -Descending | Select-Object -First 1
        if (-not $f) {
            $f = Get-ChildItem -Path $dirPath -Filter "*.sfs" -File -ErrorAction SilentlyContinue |
                 Sort-Object Length -Descending | Select-Object -First 1
        }
        if (-not $f) {
            $f = Get-ChildItem -Path $dirPath -Filter "squashfs.img" -File -ErrorAction SilentlyContinue |
                 Select-Object -First 1
        }
        if ($f) { return $f }
    }
    return Get-ChildItem -Path $Drive -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -match "^\.(squashfs|sfs|img)$" -and $_.Length -gt 50MB } |
        Sort-Object Length -Descending | Select-Object -First 1
}

# --- Main ---
Log "" ; Log "=== Linux PXE Extractor ===" "Cyan" ; Log ""
Log "  ISO : $IsoPath" ; Log "  Out : $DestDir" ; Log ""

if (-not (Test-Path $IsoPath)) { Log "[ERROR] ISO not found." "Red"; exit 1 }

try {
    Log "[1/4] Mounting ISO..." "Cyan"
    $drv = ""
    # 1) Python tarafından önceden mount edildiyse onu kullan (en güvenilir yol)
    if ($PreMountedDrive -and $PreMountedDrive.Length -eq 1) {
        if (Test-Path "$($PreMountedDrive):\") {
            $drv = $PreMountedDrive
            Log "  Using pre-mounted drive: $($drv):\" "Gray"
        }
    }
    # 2) Pre-mount yoksa veya geçersizse PowerShell ile mount dene
    if (-not $drv) {
        $m = Mount-DiskImage -ImagePath $IsoPath -PassThru -ErrorAction SilentlyContinue
        for($i=0; $i -lt 20; $i++) {
            $drv = ($m | Get-Volume -ErrorAction SilentlyContinue).DriveLetter
            if ($drv) { break }
            Start-Sleep -Milliseconds 500
        }
    }
    # 3) Hala yoksa Get-DiskImage ile attached state'i kontrol et
    if (-not $drv) {
        $diskImg = Get-DiskImage -ImagePath $IsoPath -ErrorAction SilentlyContinue
        if ($diskImg -and $diskImg.Attached) {
            $drv = ($diskImg | Get-Volume -ErrorAction SilentlyContinue).DriveLetter
        }
    }
    # 4) Son çare: Linux belirteçleri olan CD-ROM volume'lerini tara
    if (-not $drv) {
        foreach ($d in (Get-PSDrive -PSProvider FileSystem).Name) {
            if ($d.Length -ne 1) { continue }
            if ((Test-Path "$($d):\casper") -or (Test-Path "$($d):\LiveOS") -or (Test-Path "$($d):\live") -or (Test-Path "$($d):\boot\vmlinuz-lts") -or (Test-Path "$($d):\arch\boot")) {
                $drv = $d
                break
            }
        }
    }
    if (-not $drv) { Log "[ERROR] No drive letter." "Red"; exit 1 }
    $drive = "${drv}:\"
    Log "  Drive: $drive" "Gray"

    Log "[2/4] Detecting distro..." "Cyan"
    $distro = Get-DistroType -Drive $drive
    Log "  Distro: $distro" "Green"
    if ($distro -eq "generic") {
        Log "  [DEBUG] Drive contents:" "Yellow"
        $rootItems = Get-ChildItem -Path $drive -ErrorAction SilentlyContinue | Select-Object -First 20
        foreach ($it in $rootItems) {
            $typ = if ($it.PSIsContainer) { "[D]" } else { "[F]" }
            Log "    $typ $($it.Name)" "Gray"
        }
    }
    Out-File -FilePath "$DestDir\distro_hint.txt" -InputObject $distro -Encoding utf8 -Force

    $sqfsFile = Find-Squashfs -Drive $drive -Distro $distro
    if ($distro -eq "ubuntu" -and $sqfsFile -eq $null) {
        $allSqfs = Get-ChildItem -Path (Join-Path $drive "casper") -Filter "*.squashfs" -File -EA SilentlyContinue
        $layerCount = if ($allSqfs) { $allSqfs.Count } else { 0 }
        Out-File -FilePath "$DestDir\squashfs_mode.txt" -InputObject "layered" -Encoding utf8 -Force
        Log "  Ubuntu layered squashfs: $layerCount layer - full ISO mode enabled" "Yellow"
        Log "  (This structure cannot be booted with a single `fetch=` command; Casper processes all layers.)" "Yellow"
    } elseif ($sqfsFile) {
        $relPath = $sqfsFile.FullName.Substring($drive.Length).TrimStart("\").Replace("\","/")
        Out-File -FilePath "$DestDir\squashfs_path.txt" -InputObject $relPath -Encoding utf8 -Force
        Out-File -FilePath "$DestDir\squashfs_mode.txt" -InputObject "single" -Encoding utf8 -Force
        Log "  squashfs: $relPath ($([math]::Round($sqfsFile.Length/1MB,0)) MB)" "Green"
    } else {
        Out-File -FilePath "$DestDir\squashfs_mode.txt" -InputObject "iso_fallback" -Encoding utf8 -Force
        Log "  [WARN] squashfs not found - fallback: full ISO will be served." "Yellow"
    }

    if ($distro -eq "opensuse") {
        if ($sqfsFile) {
            Out-File -FilePath "$DestDir\boot_mode.txt" -InputObject "live" -Encoding utf8 -Force
            Log "  openSUSE mode: live" "Gray"
        } else {
            Out-File -FilePath "$DestDir\boot_mode.txt" -InputObject "installer" -Encoding utf8 -Force
            Log "  openSUSE mode: installer (install= method)" "Yellow"
        }
    }

    if ($distro -eq "nixos") {
        $grubCandidates = @("boot\grub\grub.cfg","boot\grub2\grub.cfg","EFI\boot\grub.cfg","EFI\BOOT\grub.cfg")
        foreach ($gf in $grubCandidates) {
            $gfPath = Join-Path $drive $gf
            if (-not (Test-Path $gfPath)) { continue }
            $content = Get-Content $gfPath -Raw -ErrorAction SilentlyContinue
            if ($content -match 'init=(\S+)') {
                Out-File -FilePath "$DestDir\nixos_init.txt" -InputObject $Matches[1] -Encoding utf8 -Force
                Log "  NixOS init: $($Matches[1])" "Green"
            }
            if ($content -match 'systemConfig=(\S+)') {
                Out-File -FilePath "$DestDir\nixos_syscfg.txt" -InputObject $Matches[1] -Encoding utf8 -Force
                Log "  NixOS syscfg: $($Matches[1])" "Gray"
            }
            break
        }
        if (-not (Test-Path "$DestDir\nixos_init.txt")) {
            Log "  [WARN] NixOS init path not found, may fall back to ISO mode." "Yellow"
        }
    }

    Log "[3/4] Searching kernel..." "Cyan"
    $kernel = Get-KernelPath -Drive $drive -Distro $distro
    if ($kernel) { Log "  Kernel: $($kernel.FullName) ($([math]::Round($kernel.Length/1MB,1)) MB)" "Green" }
    else         { Log "[ERROR] Kernel not found!" "Red" }

    Log "[4/4] Searching initrd..." "Cyan"
    $initrd = Get-InitrdPath -Drive $drive -Distro $distro
    if ($initrd) { Log "  initrd: $($initrd.FullName) ($([math]::Round($initrd.Length/1MB,1)) MB)" "Green" }
    else         { Log "[ERROR] initrd not found!" "Red" }

    if ($kernel -and $initrd) {
        Copy-Item -Path $kernel.FullName -Destination "$DestDir\vmlinuz"    -Force
        Copy-Item -Path $initrd.FullName -Destination "$DestDir\initrd.img" -Force
        $kRel = $kernel.FullName.Substring($drive.Length).TrimStart("\").Replace("\","/")
        $iRel = $initrd.FullName.Substring($drive.Length).TrimStart("\").Replace("\","/")
        Out-File -FilePath "$DestDir\kernel_path.txt" -InputObject $kRel -Encoding utf8 -Force
        Out-File -FilePath "$DestDir\initrd_path.txt" -InputObject $iRel -Encoding utf8 -Force
        Log "" ; Log "Done! Extracted to $DestDir" "Green"
    } else {
        Log "" "Red" ; Log "Failed. Large files for manual check:" "Yellow"
        Get-ChildItem -Path $drive -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -gt 1MB } | Sort-Object Length -Descending |
            Select-Object -First 15 |
            ForEach-Object { Log "  $($_.FullName) ($([math]::Round($_.Length/1MB,1)) MB)" "Gray" }
        exit 1
    }
} finally {
    Log "Extraction complete. ISO remains mounted for PXE serving." "Green"
}
"""
# ─── WinPE WIM ÇIKARMA BETİĞİ ────────────────────────────────────────────────
PS_EXTRACT_WIM_SCRIPT = r"""
param([string]$IsoPath = "", [string]$DestDir = "")

$LogPath = Join-Path $DestDir "extract.log"
function Log { param([string]$msg)
    Add-Content -Path $LogPath -Value "$(Get-Date -Format 'HH:mm:ss') $msg" -Encoding ASCII
    Write-Host $msg
}

if (-not $IsoPath -or -not (Test-Path $IsoPath)) { Log "[ERROR] ISO not found: $IsoPath"; exit 1 }
Log "Started. ISO: $IsoPath"
Log "Target : $DestDir"

try {
    Log "[1/4] Mounting ISO..."
    $mountResult = Mount-DiskImage -ImagePath $IsoPath -PassThru -ErrorAction SilentlyContinue
    $driveLetter = ""
    for($i=0; $i -lt 30; $i++) {
        $driveLetter = ($mountResult | Get-Volume -ErrorAction SilentlyContinue).DriveLetter
        if ($driveLetter) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $driveLetter) {
        $diskImg = Get-DiskImage -ImagePath $IsoPath -ErrorAction SilentlyContinue
        if ($diskImg -and $diskImg.Attached) {
            $driveLetter = ($diskImg | Get-Volume -ErrorAction SilentlyContinue).DriveLetter
        }
    }
    if (-not $driveLetter) {
        $diskImg = Get-DiskImage -ImagePath $IsoPath -ErrorAction SilentlyContinue
        if ($diskImg -and $diskImg.Attached) {
            $driveLetter = ($diskImg | Get-Disk -EA SilentlyContinue | Get-Partition -EA SilentlyContinue | Get-Volume -EA SilentlyContinue).DriveLetter | Select-Object -First 1
        }
    }
    if (-not $driveLetter) { Log "[ERROR] Could not get drive letter."; exit 1 }
    $drive = "${driveLetter}:\"
    Log "  Mounted at: $drive"

    $entries = @()

    Log "[2/4] Looking for BCD..."
    foreach ($bcdPath in @("boot\bcd","Boot\BCD","BOOT\BCD","efi\microsoft\boot\bcd","EFI\Microsoft\Boot\BCD")) {
        $bcdFile = Join-Path $drive $bcdPath
        if (-not (Test-Path $bcdFile)) { continue }
        Log "  Trying BCD: $bcdFile"
        try {
            $out = & bcdedit /store $bcdFile /enum all 2>&1
            foreach ($line in $out) {
                $s = "$line"
                if ($s -match "ramdisk=\[boot\]\\(.+?\.wim)") {
                    $wPath = $Matches[1].Trim()
                    if (-not ($entries | Where-Object { $_.WimPath -eq $wPath })) {
                        $name = [IO.Path]::GetFileNameWithoutExtension($wPath)
                        $entries += [PSCustomObject]@{ Description=$name; WimPath=$wPath }
                        Log "  BCD entry: $name -> $wPath"
                    }
                }
            }
        } catch { Log "  bcdedit failed: $_" }
        if ($entries.Count -gt 0) { Log "  BCD parse OK: $($entries.Count) WIM(s)."; break }
        Log "  No WIM entries in this BCD."
    }

    if ($entries.Count -eq 0) {
        Log "[3/4] BCD parse failed. Scanning all WIM files > 100 MB..."
        $wims = Get-ChildItem -Path $drive -Recurse -Filter "*.wim" -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Length -gt 100MB } | Sort-Object Length -Descending
        foreach ($wim in $wims) {
            $relPath = $wim.FullName.Substring($drive.Length)
            $name    = [IO.Path]::GetFileNameWithoutExtension($wim.Name)
            $sizeMB  = [math]::Round($wim.Length / 1MB)
            $entries += [PSCustomObject]@{ Description=$name; WimPath=$relPath }
            Log "  Found: $relPath ($sizeMB MB)"
        }
        Log "  Scan complete: $($entries.Count) WIM(s) found."
    } else {
        Log "[3/4] BCD provided entries, skipping WIM scan."
    }

    if ($entries.Count -eq 0) { Log "[ERROR] No WIM files found."; exit 1 }

    Log "[4/4] Copying WIMs and boot support files..."
    $bcdBios=$null; $bcdEfi=$null; $bootSdi=$null; $bootmgr=$null; $bootmgrEfi=$null
    foreach ($p in @("boot\bcd","Boot\BCD")) { $f=Join-Path $drive $p; if(Test-Path $f){$bcdBios=$f;break} }
    foreach ($p in @("efi\microsoft\boot\bcd","EFI\Microsoft\Boot\BCD")) { $f=Join-Path $drive $p; if(Test-Path $f){$bcdEfi=$f;break} }
    foreach ($p in @("boot\boot.sdi","Boot\boot.sdi")) { $f=Join-Path $drive $p; if(Test-Path $f){$bootSdi=$f;break} }
    foreach ($p in @("bootmgr.exe","bootmgr")) { $f=Join-Path $drive $p; if(Test-Path $f){$bootmgr=$f;break} }
    foreach ($p in @("efi\microsoft\boot\bootmgfw.efi","EFI\Microsoft\Boot\bootmgfw.efi","efi\boot\bootx64.efi","EFI\BOOT\BOOTX64.EFI")) { $f=Join-Path $drive $p; if(Test-Path $f){$bootmgrEfi=$f;break} }
    Log "  Boot files - BCD(BIOS):$(if($bcdBios){'OK'}else{'missing'})  BCD(EFI):$(if($bcdEfi){'OK'}else{'missing'})  boot.sdi:$(if($bootSdi){'OK'}else{'missing'})  bootmgr:$(if($bootmgr){'OK'}else{'missing'})"

    $results = @()
    foreach ($entry in $entries) {
        $wimSrc = Join-Path $drive $entry.WimPath
        if (-not (Test-Path $wimSrc)) { Log "  [SKIP] Not found: $wimSrc"; continue }
        $folderName = [IO.Path]::GetFileNameWithoutExtension($entry.WimPath)
        $subDir     = Join-Path $DestDir $folderName
        New-Item -ItemType Directory -Path $subDir -Force | Out-Null
        $sizeMB = [math]::Round((Get-Item $wimSrc).Length / 1MB)
        Log "  Copying: $($entry.WimPath) ($sizeMB MB) -> $folderName\boot.wim"
        Copy-Item $wimSrc (Join-Path $subDir "boot.wim") -Force
        if ($bcdBios)    { Copy-Item $bcdBios    (Join-Path $subDir "bcd")          -Force }
        if ($bcdEfi)     { Copy-Item $bcdEfi     (Join-Path $subDir "bcd_efi")      -Force }
        if ($bootSdi)    { Copy-Item $bootSdi    (Join-Path $subDir "boot.sdi")     -Force }
        if ($bootmgr)    { Copy-Item $bootmgr    (Join-Path $subDir "bootmgr.exe")  -Force }
        if ($bootmgrEfi) { Copy-Item $bootmgrEfi (Join-Path $subDir "bootmgfw.efi") -Force }
        $results += [PSCustomObject]@{ folder=$folderName; alias=$entry.Description }
        Log "  OK: $($entry.Description)"
    }

    $results | ConvertTo-Json -Depth 3 | Out-File (Join-Path $DestDir "wim_entries.json") -Encoding ASCII -Force
    Log "Done. $($results.Count) WIM(s) extracted."

} catch { Log "[ERROR] Unexpected error: $_"
} finally { Log "Extraction complete. ISO remains mounted for PXE serving." }
"""
# ─── LINUX ÇEKİRDEK ÇIKARMA (HAYALET/NİNJA MODU) ────────────────────────────
def _write_and_run_ps(iso_path, pre_mounted_drive=''):
    dest_dir  = os.path.dirname(iso_path)
    log_path  = os.path.join(dest_dir, 'extract.log')
    ps_script = os.path.join(BASE_DIR, 'extract_iso.ps1')

    # Log dosyasını sıfırla ve başlangıcı işaretle
    try:
        with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
            lf.write(f"Started. ISO: {iso_path}\n")
    except Exception:
        pass

    try:
        with open(ps_script, 'w', encoding='utf-8-sig') as f:
            f.write(PS_EXTRACT_SCRIPT)
    except Exception as e:
        try:
            with open(log_path, 'a', encoding='utf-8', errors='replace') as lf:
                lf.write(f"[ERROR] PS script could not be written: {e}\n")
        except Exception:
            pass
        return

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        with open(log_path, 'ab') as log_fh:
            cmd = [
                "powershell.exe", "-WindowStyle", "Hidden", "-NoProfile",
                "-ExecutionPolicy", "Bypass", "-File", ps_script,
                "-IsoPath", iso_path
            ]
            if pre_mounted_drive:
                cmd += ["-PreMountedDrive", pre_mounted_drive]
            subprocess.run(cmd, stdout=log_fh, stderr=log_fh, startupinfo=startupinfo, check=False)
    except Exception as e:
        try:
            with open(log_path, 'a', encoding='utf-8', errors='replace') as lf:
                lf.write(f"[ERROR] subprocess could not be started: {e}\n")
        except Exception:
            pass
    finally:
        if os.path.exists(ps_script):
            try: os.remove(ps_script)
            except: pass

def _extract_linux_and_regenerate(iso_path, dest_dir):
    """Linux kernel çıkarmayı arka planda çalıştırır, bitince iPXE betiğini yeniden üretir."""
    folder_name = os.path.basename(dest_dir)
    # ÖNCE eski/zombi mount'u zorla temizle (Get-DiskImage path tabanlı eşleştirme yaptığı için
    # silinmiş ISO'nun stale mount'u yeni upload'a "zaten mount" diye dönüyor)
    _unmount_iso(folder_name)
    time.sleep(0.5)
    # Şimdi temiz mount yap
    drv = _ensure_iso_mounted(folder_name)
    # PS script'e drive letter'ı geçir
    _write_and_run_ps(iso_path, pre_mounted_drive=drv or '')
    generate_ipxe_script()

def _get_wim_image_count(wimlib, wim_file, si):
    """boot.wim icindeki image sayisini dondurur (enjeksiyon icin dogru indeks tespiti)."""
    try:
        r = subprocess.run([wimlib, 'info', wim_file],
            capture_output=True, text=True, startupinfo=si, timeout=15)
        count = sum(1 for l in r.stdout.splitlines() if l.strip().startswith('Index:'))
        return count if count > 0 else 1
    except Exception: return 1

def _extract_wim_and_regenerate(iso_path, dest_dir):
    """WIM çıkarmayı arka planda çalıştırır, bitince rclone/davinst enjekte eder ve iPXE betiğini yeniden üretir."""
    # Eski/zombi mount'u temizle (path tabanlı stale state sorunu)
    folder_name = os.path.basename(dest_dir)
    _unmount_iso(folder_name)
    time.sleep(0.5)
    extract_wim_from_iso(iso_path, dest_dir)

    # Çıkarılan her boot.wim'e rclone + davinst enjekte et
    wimlib = os.path.join(BASE_DIR, 'pxe', 'TOOLS', 'wimlib-imagex.exe')
    rclone_dir = os.path.join(BASE_DIR, 'pxe', 'TOOLS', 'MS', 'rclone')
    if os.path.exists(wimlib) and os.path.exists(rclone_dir):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        log_path = os.path.join(dest_dir, 'extract.log')
        def _log(msg):
            try:
                with open(log_path, 'a', encoding='ascii', errors='replace') as lf:
                    lf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
            except Exception: pass
        for sub in os.listdir(dest_dir):
            sub_path = os.path.join(dest_dir, sub)
            wim_file = os.path.join(sub_path, 'boot.wim')
            if os.path.isdir(sub_path) and os.path.exists(wim_file):
                _log(f"  Injecting Rclone/davinst into {sub}/boot.wim...")
                try:
                    os.chmod(wim_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                except Exception: pass
                img_count = _get_wim_image_count(wimlib, wim_file, si)
                img_idx = str(img_count)
                # WIM mimarisini tespit et (x86 WinPE icin UCRT enjeksiyonu gerekli)
                r_info = subprocess.run([wimlib, 'info', wim_file, img_idx],
                    capture_output=True, text=True, startupinfo=si, timeout=15)
                info_lower = r_info.stdout.lower()
                is_x86_wim = ('x86' in info_lower or 'i386' in info_lower) and 'x86_64' not in info_lower and 'amd64' not in info_lower
                wim_arch_str = 'x86' if is_x86_wim else 'x64'
                _log(f"  WIM arch: {wim_arch_str}")
                # arch bilgisini wim_entries.json'a kaydet (iPXE menü filtresi için)
                wim_entries_path = os.path.join(dest_dir, 'wim_entries.json')
                if os.path.exists(wim_entries_path):
                    try:
                        with open(wim_entries_path, 'r', encoding='utf-8') as _wef:
                            _entries = json.load(_wef)
                        for _e in (_entries if isinstance(_entries, list) else [_entries]):
                            if _e.get('folder') == sub:
                                _e['arch'] = wim_arch_str
                                break
                        with open(wim_entries_path, 'w', encoding='utf-8') as _wef:
                            json.dump(_entries, _wef, indent=2, ensure_ascii=False)
                    except Exception: pass
                # Rclone klasörünü enjekte et (ucrt_x86 / ucrt_x64 alt klasörleri hariç)
                inj_cmd = ''
                for _item in os.listdir(rclone_dir):
                    if _item.lower() in ('ucrt_x86', 'ucrt_x64'):
                        continue
                    _item_path = os.path.join(rclone_dir, _item)
                    inj_cmd += f'add "{_item_path}" "/Windows/System32/rclone/{_item}"\n'
                # UCRT enjeksiyonu — x86 ve x64 için uygun klasörden
                sysroot = os.environ.get('SystemRoot', 'C:\\Windows')
                if is_x86_wim:
                    ucrt_search_dirs = [
                        os.path.join(rclone_dir, 'ucrt_x86'),
                        os.path.join(sysroot, 'SysWOW64', 'downlevel'),
                        os.path.join(sysroot, 'SysWOW64'),
                    ]
                else:
                    ucrt_search_dirs = [
                        os.path.join(rclone_dir, 'ucrt_x64'),
                        os.path.join(sysroot, 'System32', 'downlevel'),
                        os.path.join(sysroot, 'System32'),
                    ]
                ucrt_names = [
                    f for d in ucrt_search_dirs if os.path.isdir(d)
                    for f in os.listdir(d)
                    if f.lower().endswith('.dll') and (
                        f.lower().startswith('api-ms-win-crt-') or
                        f.lower().startswith('api-ms-win-core-') or
                        f.lower() in ('ucrtbase.dll', 'vcruntime140.dll')
                    )
                ]
                seen = set(); ucrt_names_unique = []
                for n in ucrt_names:
                    if n.lower() not in seen:
                        seen.add(n.lower()); ucrt_names_unique.append(n)
                for dll in ucrt_names_unique:
                    for search_dir in ucrt_search_dirs:
                        dll_path = os.path.join(search_dir, dll)
                        if os.path.exists(dll_path):
                            inj_cmd += f'add "{dll_path}" "/Windows/System32/{dll}"\n'
                            break
                _log(f"  Injecting UCRT/API Set DLLs ({'x86' if is_x86_wim else 'x64'})...")
                r_inj = subprocess.run(
                    [wimlib, 'update', wim_file, img_idx],
                    input=inj_cmd, capture_output=True, text=True,
                    startupinfo=si, timeout=120)
                if r_inj.returncode == 0:
                    _log(f"  Rclone injected into {sub}/boot.wim (image {img_idx}) successfully.")
                else:
                    _log(f"  [WARN] Rclone inject failed for {sub}: {r_inj.stderr.strip()}")
        _log("=== All done. ===")

    generate_ipxe_script()
    folder_name = os.path.basename(dest_dir)
    _ensure_iso_mounted(folder_name)

def _extract_win_iso_and_regenerate(iso_path, dest_dir):
    """Windows Setup ISO'sundan boot.wim çıkarır, WebDAV için wimlib ile saniyeler içinde hazırlar."""
    log_path = os.path.join(dest_dir, 'extract.log')
    # Her çalıştırmada logu sıfırla
    try:
        open(log_path, 'w', encoding='ascii', errors='replace').close()
    except Exception:
        pass
    def log(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        try:
            with open(log_path, 'a', encoding='ascii', errors='replace') as lf:
                lf.write(line + '\n')
        except Exception: pass
    log("Started. Windows ISO extraction & WebClient Integration (Fast wimlib method).")
    log(f"ISO: {iso_path}")
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    drv = None
    try:
        _defender_exclude(iso_path)
        _defender_exclude(os.path.dirname(iso_path))
        folder_name = os.path.basename(os.path.dirname(iso_path))
        # Eski/zombi mount'u temizle (path tabanlı stale state sorunu)
        _unmount_iso(folder_name)
        time.sleep(0.5)
        drv = _mount_iso(folder_name)
        if not drv:
            log("[ERROR] Mount failed: Drive letter could not be resolved.")
            return
        log(f"  Mounted at: {drv}:\\")
        
        # sources/boot.wim çıkar
        src_wim = os.path.join(f"{drv}:\\", 'sources', 'boot.wim')
        if not os.path.exists(src_wim):
            src_wim = os.path.join(f"{drv}:\\", 'sources', 'Boot.wim')
        
        if os.path.exists(src_wim):
            dst_wim = os.path.join(dest_dir, 'boot.wim')
            log(f"  Copying boot.wim ({os.path.getsize(src_wim)//1024//1024} MB)...")
            shutil.copy2(src_wim, dst_wim)
            
            # ISO'dan kopyalanan dosya read-only olabilir — wimlib için kaldır
            try:
                os.chmod(dst_wim, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            except Exception: pass
            log("  boot.wim OK")

            # Adım 1: Rclone ve WinFsp dosyalarını boot.wim'e enjekte et
            wimlib = os.path.join(BASE_DIR, 'pxe', 'TOOLS', 'wimlib-imagex.exe')
            rclone_dir = os.path.join(BASE_DIR, 'pxe', 'TOOLS', 'MS', 'rclone')
            if os.path.exists(rclone_dir):
                log("  Injecting Rclone and WinFsp into boot.wim System32...")
                img_count = _get_wim_image_count(wimlib, dst_wim, si)
                img_idx = str(img_count)
                # Rclone klasörünü enjekte et (ucrt_x86 alt klasörü hariç)
                # Rclone klasörünü enjekte et (ucrt_x86 / ucrt_x64 alt klasörleri hariç)
                inj_cmd = ''
                for _item in os.listdir(rclone_dir):
                    if _item.lower() in ('ucrt_x86', 'ucrt_x64'):
                        continue
                    _item_path = os.path.join(rclone_dir, _item)
                    inj_cmd += f'add "{_item_path}" "/Windows/System32/rclone/{_item}"\n'
                # WIM mimarisi tespiti + UCRT enjeksiyonu
                r_info = subprocess.run([wimlib, 'info', dst_wim, img_idx],
                    capture_output=True, text=True, startupinfo=si, timeout=15)
                info_lower = r_info.stdout.lower()
                is_x86_wim = ('x86' in info_lower or 'i386' in info_lower) and 'x86_64' not in info_lower and 'amd64' not in info_lower
                log(f"  WIM arch: {'x86' if is_x86_wim else 'x64'}")
                sysroot = os.environ.get('SystemRoot', 'C:\\Windows')
                if is_x86_wim:
                    ucrt_search_dirs = [
                        os.path.join(rclone_dir, 'ucrt_x86'),
                        os.path.join(sysroot, 'SysWOW64', 'downlevel'),
                        os.path.join(sysroot, 'SysWOW64'),
                    ]
                else:
                    ucrt_search_dirs = [
                        os.path.join(rclone_dir, 'ucrt_x64'),
                        os.path.join(sysroot, 'System32', 'downlevel'),
                        os.path.join(sysroot, 'System32'),
                    ]
                ucrt_names = [
                    f for d in ucrt_search_dirs if os.path.isdir(d)
                    for f in os.listdir(d)
                    if f.lower().endswith('.dll') and (
                        f.lower().startswith('api-ms-win-crt-') or
                        f.lower().startswith('api-ms-win-core-') or
                        f.lower() in ('ucrtbase.dll', 'vcruntime140.dll')
                    )
                ]
                seen = set(); ucrt_names_unique = []
                for n in ucrt_names:
                    if n.lower() not in seen:
                        seen.add(n.lower()); ucrt_names_unique.append(n)
                for dll in ucrt_names_unique:
                    for search_dir in ucrt_search_dirs:
                        dll_path = os.path.join(search_dir, dll)
                        if os.path.exists(dll_path):
                            inj_cmd += f'add "{dll_path}" "/Windows/System32/{dll}"\n'
                            break
                log(f"  Injecting UCRT/API Set DLLs ({'x86' if is_x86_wim else 'x64'})...")
                r_dav = subprocess.run(
                    [wimlib, 'update', dst_wim, img_idx],
                    input=inj_cmd, capture_output=True, text=True,
                    startupinfo=si, timeout=60)
                if r_dav.returncode == 0:
                    log("  Rclone injected successfully.")
                else:
                    log(f"  [WARN] Rclone inject failed: {r_dav.stderr.strip()}")
            else:
                log(f"  [WARN] {rclone_dir} not found. Rclone could not be injected.")
        else:
            log("[WARN] sources/boot.wim not found - wimboot will use generic")
        log("Done.")
        log("=== All done. ===")
    except Exception as e:
        log(f"[ERROR] {e}")
    finally:
        # ISO mount'lu kalır — istemciler WebDAV/HTTP üzerinden erişecek
        if drv:
            with _iso_mounts_lock:
                _iso_mounts[os.path.basename(dest_dir)] = drv
            _defender_exclude(f"{drv}:\\")
            _defender_exclude(iso_path)
            log(f"  ISO remains mounted at {drv}:\\ for WebDAV serving.")
        
    generate_ipxe_script()
    folder_name = os.path.basename(dest_dir)
    _ensure_iso_mounted(folder_name)

def extract_wim_from_iso(iso_path, dest_dir):
    """WIM_MODIFIED ISO içindeki boot WIM dosyalarını BCD'den okuyarak ayıklar."""
    ps_script = os.path.join(BASE_DIR, 'extract_wim.ps1')
    log_path  = os.path.join(dest_dir, 'extract.log')
    # Her çalıştırmada logu sıfırla
    try:
        open(log_path, 'w', encoding='utf-8').close()
    except Exception:
        pass
    try:
        with open(ps_script, 'w', encoding='utf-8') as f:
            f.write(PS_EXTRACT_WIM_SCRIPT)
    except Exception as e:
        try:
            with open(log_path, 'w', encoding='utf-8') as lf:
                lf.write(f"[ERROR] PS script could not be written: {e}\n")
        except: pass
        return

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        subprocess.run([
            "powershell.exe", "-WindowStyle", "Hidden", "-NoProfile",
            "-ExecutionPolicy", "Bypass", "-File", ps_script,
            "-IsoPath", iso_path, "-DestDir", dest_dir
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
           startupinfo=startupinfo, check=False)
    except Exception as e:
        try:
            with open(log_path, 'a', encoding='utf-8') as lf:
                lf.write(f"[ERROR] subprocess could not be started: {e}\n")
        except: pass
    finally:
        if os.path.exists(ps_script):
            try: os.remove(ps_script)
            except: pass


def scan_and_extract_manual_linux():
    if not os.path.exists(ISO_LIN_DIR):
        return

    def _do():
        for folder in os.listdir(ISO_LIN_DIR):
            folder_path = os.path.join(ISO_LIN_DIR, folder)
            if os.path.isdir(folder_path):
                iso_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.iso')]
                if iso_files:
                    iso_path = os.path.join(folder_path, iso_files[0])
                    _write_and_run_ps(iso_path)
        generate_ipxe_script()

    threading.Thread(target=_do, daemon=True).start()

# ─── Pencere gizleme ────────────────────────────────────────────────────────
def _hide_window_by_pid(pid: int, retries: int = 8, delay: float = 0.8):
    user32 = ctypes.windll.user32
    SW_HIDE          = 0
    GWL_EXSTYLE      = -20
    WS_EX_APPWINDOW  = 0x00040000
    WS_EX_TOOLWINDOW = 0x00000080

    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                   ctypes.wintypes.HWND,
                                   ctypes.wintypes.LPARAM)
    found = [False]

    def callback(hwnd, _):
        win_pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
        if win_pid.value == pid:
            found[0] = True
            user32.ShowWindow(hwnd, SW_HIDE)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        return True

    for _ in range(retries):
        found[0] = False
        user32.EnumWindows(EnumProc(callback), 0)
        if found[0]:
            break
        time.sleep(delay)

# ─── pxesrv başlat / durdur ─────────────────────────────────────────────────
def internal_start_pxe():
    global pxe_process
    try:
        result = subprocess.check_output(
            ['tasklist', '/FI', 'IMAGENAME eq pxesrv.exe'],
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode('latin-1')
        if 'pxesrv.exe' in result:
            return
    except Exception:
        pass

    if not os.path.exists(PXESRV_EXE):
        return

    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags     = subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0   # SW_HIDE
        pxe_process = subprocess.Popen(
            [PXESRV_EXE],
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=PXE_DIR
        )
        threading.Thread(
            target=_hide_window_by_pid,
            args=(pxe_process.pid,),
            daemon=True
        ).start()
    except Exception as e:
        pass

def internal_stop_pxe():
    global pxe_process
    try:
        subprocess.run(
            ['taskkill', '/F', '/IM', 'pxesrv.exe'],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(1.5) 
    except Exception:
        pass
    pxe_process = None

# ─── Yardımcılar ────────────────────────────────────────────────────────────
ACTIVE_CLIENTS = {}
def _mark_active(ip): ACTIVE_CLIENTS[ip] = time.time()
def _get_active_clients():
    now = time.time()
    expired = [ip for ip, t in ACTIVE_CLIENTS.items() if now - t > 300]
    for ip in expired: del ACTIVE_CLIENTS[ip]
    
    active_ips = set(ACTIVE_CLIENTS.keys())
    try:
        out = subprocess.check_output(
            ['netstat', '-n', '-p', 'tcp'], 
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode('latin-1')
        for line in out.splitlines():
            if 'ESTABLISHED' in line:
                parts = line.split()
                if len(parts) >= 4:
                    loc = parts[1]; rem = parts[2]
                    if loc.endswith(':80'):
                        cip = rem.split(':')[0]
                        if cip not in ('127.0.0.1', '0.0.0.0'): active_ips.add(cip)
    except: pass
    return list(active_ips)

def _get_metadata():
    path = os.path.join(PXE_DIR, 'metadata.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

def _save_metadata(data):
    path = os.path.join(PXE_DIR, 'metadata.json')
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

def _get_ethernet_ip():
    """Ethernet (kablolu) arayüzünün IPv4 adresini döner.
    Önce Windows NIC isimlerine bakılır, bulunamazsa varsayılan çıkış IP'si kullanılır."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        ps = (
            "Get-NetAdapter | "
            "Where-Object { $_.Status -eq 'Up' -and "
            "  ($_.InterfaceDescription -notmatch 'Wi-?Fi|Wireless|VPN|Virtual|TAP|Loopback|Bluetooth|Hyper-V') -and "
            "  ($_.Name -notmatch 'Wi-?Fi|Wireless|VPN|vEthernet|Loopback') } | "
            "Sort-Object -Property Speed -Descending | Select-Object -First 1 | "
            "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty IPAddress"
        )
        r = subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps],
            capture_output=True, text=True, startupinfo=si, timeout=8)
        ip = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ''
        if ip and ip.count('.') == 3 and not ip.startswith('169.254'):
            return ip
    except Exception:
        pass
    # Fallback: varsayılan çıkış arayüzünün IP'si
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip.count('.') == 3 and not ip.startswith('127.') and not ip.startswith('169.254'):
            return ip
    except Exception:
        pass
    return None

def _is_local_ip(ip):
    """Verilen IP bu makinenin herhangi bir arayüzüne ait mi?"""
    try:
        hostname = socket.gethostname()
        local_ips = set()
        for info in socket.getaddrinfo(hostname, None):
            local_ips.add(info[4][0])
        # Tüm arayüzleri tara (getaddrinfo bazen eksik kalır)
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            r = subprocess.run(
                ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
                 "Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress"],
                capture_output=True, text=True, startupinfo=si, timeout=8)
            for line in r.stdout.splitlines():
                line = line.strip()
                if line: local_ips.add(line)
        except Exception:
            pass
        return ip in local_ips
    except Exception:
        return False

def _load_app_settings():
    defaults = {'domain': '192.168.1.1', 'language': 'Turkish', 'theme': 'light',
                'default_boot': 'HDD', 'countdown': 10, 'file_order': []}
    path = os.path.join(PXE_DIR, 'app_settings.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    defaults.update(loaded)
        except: pass
        # Kayıtlı IP bu makinede yoksa (başka PC'ye taşındı) → ethernet IP ile güncelle
        saved_ip = defaults.get('domain', '')
        if saved_ip and not _is_local_ip(saved_ip):
            eth_ip = _get_ethernet_ip()
            if eth_ip:
                defaults['domain'] = eth_ip
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(defaults, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass
    else:
        # İlk çalıştırma: app_settings.json yok — ethernet IP'yi otomatik doldur ve kaydet
        eth_ip = _get_ethernet_ip()
        if eth_ip:
            defaults['domain'] = eth_ip
        try:
            os.makedirs(PXE_DIR, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(defaults, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
    return defaults

def generate_ipxe_script(domain=None):
    settings = _load_app_settings()
    if not domain or not str(domain).strip():
        domain = settings.get('domain')
    if not domain or not str(domain).strip():
        domain = '10.50.1.57' # Kullanıcı boş bırakırsa sistemi çökertmemek için kurtarıcı IP

    default_boot = settings.get('default_boot') or 'HDD'
    try:
        countdown_sec = int(settings.get('countdown', 10))
    except (ValueError, TypeError):
        countdown_sec = 10
    if countdown_sec < 0: countdown_sec = 0
    timeout_ms = countdown_sec * 1000
        
    boot_url = f"http://{domain}"

    files = []; metadata = _get_metadata()
    if os.path.exists(ISO_WIN_DIR):
        for f in os.listdir(ISO_WIN_DIR):
            p = os.path.join(ISO_WIN_DIR, f)
            # Yeni yapı: alt klasör + source.iso
            if os.path.isdir(p) and os.path.exists(os.path.join(p, 'source.iso')):
                files.append({'name': f, 'alias': metadata.get(f, f), 'type': 'ISO_WIN'})
            # Eski yapı: düz .iso (geriye dönük uyumluluk)
            elif os.path.isfile(p) and f.lower().endswith('.iso'):
                files.append({'name': f, 'alias': metadata.get(f, f), 'type': 'ISO_WIN'})
            
    if os.path.exists(ISO_LIN_DIR):
        for entry in os.listdir(ISO_LIN_DIR):
            p = os.path.join(ISO_LIN_DIR, entry)
            if os.path.isdir(p):
                iso_files = [x for x in os.listdir(p) if x.lower().endswith('.iso')]
                if iso_files:
                    files.append({'name': entry, 'iso_file': iso_files[0], 'is_dir': True, 'alias': metadata.get(entry, entry), 'type': 'ISO_LINUX'})
            elif os.path.isfile(p) and entry.lower().endswith('.iso'):
                files.append({'name': entry, 'iso_file': entry, 'is_dir': False, 'alias': metadata.get(entry, entry), 'type': 'ISO_LINUX'})

    if os.path.exists(WIM_DIR):
        for entry in os.listdir(WIM_DIR):
            folder_path = os.path.join(WIM_DIR, entry)
            if not os.path.isdir(folder_path):
                continue
            mod_flag = os.path.join(folder_path, 'modified.flag')
            iso_p = os.path.join(folder_path, 'source.iso')
            wim_p = os.path.join(folder_path, 'boot.wim')
            if os.path.exists(mod_flag) and os.path.exists(iso_p):
                files.append({'name': entry, 'alias': metadata.get(entry, entry), 'type': 'WIM_MODIFIED'})
            elif os.path.exists(wim_p):
                files.append({'name': entry, 'alias': metadata.get(entry, entry), 'type': 'WIM'})

    menu_lines = []; boot_lines = []

    # Kayıtlı sırayı uygula
    saved_order = settings.get('file_order', [])
    if saved_order:
        order_map = {name: i for i, name in enumerate(saved_order)}
        files.sort(key=lambda f: order_map.get(f['name'], len(saved_order)))

    # Kategorilere göre grupla
    winpe_files  = [f for f in files if f['type'] in ('WIM', 'WIM_MODIFIED')]
    win_files    = [f for f in files if f['type'] == 'ISO_WIN']
    linux_files  = [f for f in files if f['type'] == 'ISO_LINUX']

    def add_winpe_group(group):
        if not group: return
        menu_lines.append(f"item")
        menu_lines.append(f"item --gap ${{fg_cya}}${{bold}} WinPE")
        for f in group:
            safe_id = f['name'].replace('.', '_').replace(' ', '_')
            item_id = f"boot_{f['type'].lower()}_{safe_id}"
            if f['type'] == 'WIM_MODIFIED':
                # wim_entries.json'dan sub-entryleri oku
                folder_path      = os.path.join(WIM_DIR, f['name'])
                wim_entries_path = os.path.join(folder_path, 'wim_entries.json')
                wim_entries = []
                if os.path.exists(wim_entries_path):
                    try:
                        with open(wim_entries_path, 'r', encoding='utf-8') as wf2:
                            data = json.load(wf2)
                            wim_entries = data if isinstance(data, list) else [data]
                    except Exception:
                        pass
                if not wim_entries:
                    for sub in (os.listdir(folder_path) if os.path.exists(folder_path) else []):
                        sub_path = os.path.join(folder_path, sub)
                        if os.path.isdir(sub_path) and os.path.exists(os.path.join(sub_path, 'boot.wim')):
                            wim_entries.append({'folder': sub, 'alias': sub})
                for wim in wim_entries:
                    wim_folder = wim.get('folder', '')
                    wim_alias  = wim.get('alias', wim_folder)
                    wim_arch   = wim.get('arch', 'x64')  # varsayılan x64: yeni eklenmeyenlerde güvenli
                    wim_safe   = wim_folder.replace('.', '_').replace(' ', '_')
                    wim_id     = f"boot_wim_mod_{safe_id}_{wim_safe}"
                    if wim_arch == 'x86':
                        # x86 WIM: EFI modunda menüde görünmez, BIOS modunda görünür
                        menu_lines.append(f"iseq ${{platform}} efi || item {wim_id} ${{bold}}${{fg_whi}}\t\t{wim_alias}")
                    else:
                        menu_lines.append(f"item {wim_id} ${{bold}}${{fg_whi}}\t\t{wim_alias}")
            else:
                menu_lines.append(f"item {item_id} ${{bold}}${{fg_whi}}\t\t{f['alias']}")

    def add_group(group, header):
        if not group: return
        menu_lines.append(f"item")
        menu_lines.append(f"item --gap ${{fg_cya}}${{bold}} {header}")
        for f in group:
            safe_id = f['name'].replace('.', '_').replace(' ', '_')
            item_id = f"boot_{f['type'].lower()}_{safe_id}"
            menu_lines.append(f"item {item_id} ${{bold}}${{fg_whi}}\t\t{f['alias']}")

    add_winpe_group(winpe_files)
    add_group(win_files,    'Windows Setup')
    add_group(linux_files,  'Linux Setup')

    # Boot bloklarını kategoriye göre sıralı işle
    ordered_files = winpe_files + win_files + linux_files
    for f in ordered_files:
        safe_id = f['name'].replace('.', '_').replace(' ', '_')
        item_id = f"boot_{f['type'].lower()}_{safe_id}"

        if f['type'] in ('ISO_WIN', 'WIM_MODIFIED'):
            cmd_dir  = os.path.join(PXE_DIR, 'TOOLS', 'MS', 'dynamic', safe_id)
            os.makedirs(cmd_dir, exist_ok=True)
            is_setup = (f['type'] == 'ISO_WIN')

            # ── ipxe.cfg ─────────────────────────────────────────────────────
            try:
                http_ip = socket.gethostbyname(domain)
            except Exception:
                http_ip = domain

            if is_setup:
                # Windows Setup: WebDAV
                with open(os.path.join(cmd_dir, 'ipxe.cfg'), 'w', encoding='utf-8') as sf:
                    sf.write(f"SERVER_IP={http_ip}\r\nHTTP_PORT=8080\r\nISO_DIR={f['name']}\r\nMODE=SETUP\r\n")
            else:
                # WinPE: WebDAV
                with open(os.path.join(cmd_dir, 'ipxe.cfg'), 'w', encoding='utf-8') as sf:
                    sf.write(f"SERVER_IP={http_ip}\r\nHTTP_PORT=8080\r\nISO_DIR={f['name']}\r\nMODE=WINPE\r\n")

            # ── WinSetup.cmd ─────────────────────────────────────────────────
            CFG_HEADER = (
                ":: DO NOT EDIT THIS FILE IF YOU DON'T KNOW WHAT YOU'RE DOING. IT MAY BREAK THE SYSTEM.\r\n"
                "@echo off\r\nsetlocal enabledelayedexpansion\r\n"
                "title iPXE Manager\r\ncolor 1f\r\n"
                "echo.\r\necho\t\tDO NOT CLOSE THIS CMD SCREEN\r\necho.\r\n"
                "set \"CFG_PATH=X:\\Windows\\System32\\ipxe.cfg\"\r\n"
            )
            DRIVE_FIND = (
                "set \"DRIVE=\"\r\n"
                "for %%A in (Y X W V U T S R Q P O N M L K) do (\r\n"
                "    if not defined DRIVE ( if not exist %%A:\\ set \"DRIVE=%%A\" )\r\n)\r\n"
            )

            if not is_setup:
                # ── WinPE (WIM_MODIFIED): WinFsp + Rclone + WebDAV mount ──
                winsetup = (
                    CFG_HEADER +
					"set \"SERVER_IP=\"\r\nset \"HTTP_PORT=8080\"\r\nset \"ISO_DIR=\"\r\n"
                    "if exist \"%CFG_PATH%\" (\r\n"
                    "    for /f \"usebackq tokens=1,2 delims==\" %%a in (\"%CFG_PATH%\") do (\r\n"
                    "        if /i \"%%a\"==\"SERVER_IP\" set \"SERVER_IP=%%b\"\r\n"
                    "        if /i \"%%a\"==\"HTTP_PORT\" set \"HTTP_PORT=%%b\"\r\n"
                    "        if /i \"%%a\"==\"ISO_DIR\"   set \"ISO_DIR=%%b\"\r\n"
                    "    )\r\n"
                    ")\r\n"
                    "if \"%SERVER_IP%\"==\"\" set /p \"SERVER_IP=[?] Server IP: \"\r\n"
                    "if \"%ISO_DIR%\"==\"\"  set /p \"ISO_DIR=[?] ISO Folder: \"\r\n"
                    "echo WebDAV Server: %SERVER_IP%:%HTTP_PORT% ISO: %ISO_DIR%\r\n"
                    "echo.\r\n"
                    "echo [+] Initializing Network...\r\n"
                    "wpeutil InitializeNetwork >nul\r\n"
                    "ping 127.0.0.1 -n 4 >nul\r\n"
                    "echo [+] Detecting architecture...\r\n"
                    "set \"ARCH=amd64\"\r\n"
                    "if /i \"%PROCESSOR_ARCHITECTURE%\"==\"x86\" set \"ARCH=x86\"\r\n"
                    "echo     Architecture: %ARCH%\r\n"
                    + DRIVE_FIND +
                    "set \"DAV_URL=http://%SERVER_IP%:%HTTP_PORT%/dav/%ISO_DIR%/\"\r\n"
                    "echo.\r\n"
                    "echo [+] Trying WebClient (native WebDAV)...\r\n"
                    "net start WebClient >nul 2>&1\r\n"
                    "echo [+] Mapping %DRIVE%: via WebClient...\r\n"
                    "net use %DRIVE%: \\\\%SERVER_IP%@%HTTP_PORT%\\DavWWWRoot\\dav\\%ISO_DIR% /persistent:no >nul 2>&1\r\n"
                    "if exist \"%DRIVE%:\\\" goto :MOUNT_OK\r\n"
                    "echo [!] WebClient mount failed. Falling back to Rclone...\r\n"
                    "net use %DRIVE%: /delete >nul 2>&1\r\n"
                    "\r\n"
                    ":USE_RCLONE\r\n"
                    "echo [+] Installing WinFsp Driver...\r\n"
                    "if \"%ARCH%\"==\"amd64\" (\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x64.sys\" \"%systemroot%\\system32\\drivers\\\" >nul\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x64.dll\" \"%systemroot%\\system32\\\" >nul\r\n"
                    ") else (\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x86.sys\" \"%systemroot%\\system32\\drivers\\\" >nul\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x86.dll\" \"%systemroot%\\system32\\\" >nul\r\n"
                    ")\r\n"
                    "\"%SystemRoot%\\System32\\rclone\\davinst_%ARCH%.exe\"\r\n"
                    "ping 127.0.0.1 -n 2 >nul\r\n"
                    "echo [+] Mounting WebDAV to %DRIVE%: via Rclone...\r\n"
                    "echo Set WshShell = CreateObject(\"WScript.Shell\") > \"%~dp0rclone_hidden.vbs\"\r\n"
                    "echo WshShell.Run Chr(34) ^& \"%SystemRoot%\\System32\\rclone\\rclone_%ARCH%.exe\" ^& Chr(34) ^& \" mount :webdav: %DRIVE%: --webdav-url %DAV_URL% --read-only --file-perms 0777 --vfs-cache-mode writes --no-checksum --no-modtime --dir-cache-time 1h --vfs-read-chunk-size 32M --retries 1 --log-level CRITICAL --volname \"\"WinPE ISO\"\"\", 0, False >> \"%~dp0rclone_hidden.vbs\"\r\n"
                    "wscript.exe \"%~dp0rclone_hidden.vbs\"\r\n"
                    "ping 127.0.0.1 -n 4 >nul\r\n"
                    "\r\n"
                    ":MOUNT_OK\r\n"
                    "if exist \"%DRIVE%:\\\" (\r\n"
                    "    echo [+] ISO mounted at %DRIVE%: WinPE ready.\r\n"
                    "    ping 127.0.0.1 -n 2 >nul\r\n"
                    "    exit\r\n"
                    ") else (\r\n"
                    "    echo [!] Mount failed. Drive %DRIVE%: not accessible.\r\n"
                    "    cmd /k\r\n"
                    ")\r\n"
                )
            else:
                # ── Windows Setup (ISO_WIN): WinFsp + Rclone + setup.exe ──
                winsetup = (
                    CFG_HEADER +
                    "set \"SERVER_IP=\"\r\nset \"HTTP_PORT=8080\"\r\nset \"ISO_DIR=\"\r\n"
                    "if exist \"%CFG_PATH%\" (\r\n"
                    "    for /f \"usebackq tokens=1,2 delims==\" %%a in (\"%CFG_PATH%\") do (\r\n"
                    "        if /i \"%%a\"==\"SERVER_IP\"  set \"SERVER_IP=%%b\"\r\n"
                    "        if /i \"%%a\"==\"HTTP_PORT\" set \"HTTP_PORT=%%b\"\r\n"
                    "        if /i \"%%a\"==\"ISO_DIR\"    set \"ISO_DIR=%%b\"\r\n"
                    "    )\r\n)\r\n"
                    "if \"%SERVER_IP%\"==\"\" set /p \"SERVER_IP=[?] Server IP: \"\r\n"
                    "echo WebDAV Server: %SERVER_IP%:%HTTP_PORT% ISO: %ISO_DIR%\r\necho.\r\n"
                    "echo [+] Initializing Network...\r\n"
                    "wpeutil InitializeNetwork >nul\r\nping 127.0.0.1 -n 4 >nul\r\n"
                    "echo [+] Detecting architecture...\r\n"
                    "set \"ARCH=amd64\"\r\n"
                    "if /i \"%PROCESSOR_ARCHITECTURE%\"==\"x86\" set \"ARCH=x86\"\r\n"
                    "echo     Architecture: %ARCH%\r\n"
                    + DRIVE_FIND +
                    "set \"DAV_URL=http://%SERVER_IP%:%HTTP_PORT%/dav/%ISO_DIR%/\"\r\n"
                    "echo.\r\n"
                    "echo [+] Trying WebClient (native WebDAV)...\r\n"
                    "net start WebClient >nul 2>&1\r\n"
                    "echo [+] Mapping %DRIVE%: via WebClient...\r\n"
                    "net use %DRIVE%: \\\\%SERVER_IP%@%HTTP_PORT%\\DavWWWRoot\\dav\\%ISO_DIR% /persistent:no >nul 2>&1\r\n"
                    "if exist \"%DRIVE%:\\\" goto :MOUNT_OK\r\n"
                    "echo [!] WebClient mount failed. Falling back to Rclone...\r\n"
                    "net use %DRIVE%: /delete >nul 2>&1\r\n"
                    "\r\n"
                    ":USE_RCLONE\r\n"
                    "echo [+] Installing WinFsp Driver...\r\n"
                    "if \"%ARCH%\"==\"amd64\" (\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x64.sys\" \"%systemroot%\\system32\\drivers\\\" >nul\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x64.dll\" \"%systemroot%\\system32\\\" >nul\r\n"
                    ") else (\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x86.sys\" \"%systemroot%\\system32\\drivers\\\" >nul\r\n"
                    "    copy /y \"%SystemRoot%\\System32\\rclone\\winfsp-x86.dll\" \"%systemroot%\\system32\\\" >nul\r\n"
                    ")\r\n"
                    "\"%SystemRoot%\\System32\\rclone\\davinst_%ARCH%.exe\"\r\n"
                    "ping 127.0.0.1 -n 2 >nul\r\n"
                    "echo [+] Mounting WebDAV to %DRIVE%: via Rclone...\r\n"
                    "start /b \"\" \"%SystemRoot%\\System32\\rclone\\rclone_%ARCH%.exe\" mount :webdav: %DRIVE%: --webdav-url %DAV_URL% --read-only --file-perms 0777 --vfs-cache-mode writes --no-checksum --no-modtime --dir-cache-time 1h --vfs-read-chunk-size 32M --retries 1 --log-level CRITICAL --volname \"Win_ISO\"\r\n"
                    "ping 127.0.0.1 -n 4 >nul\r\n"
                    "\r\n"
                    ":MOUNT_OK\r\n"
                    "if exist \"%DRIVE%:\\\" (\r\n"
                    "    echo [+] Mounted at %DRIVE%:\r\n"
                    ") else (\r\n"
                    "    echo [!] Mount failed. Drive %DRIVE%: not accessible.\r\n"
                    "    cmd /k\r\n)\r\n"
                    "echo.\r\necho [+] Done. ISO available at %DRIVE%:\r\necho.\r\n"
                    "echo [+] Applying Windows 11 Requirement Bypasses...\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\LabConfig\" /f >nul\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\LabConfig\" /v \"BypassRAMCheck\" /t REG_DWORD /d 1 /f >nul\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\LabConfig\" /v \"BypassTPMCheck\" /t REG_DWORD /d 1 /f >nul\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\LabConfig\" /v \"BypassSecureBootCheck\" /t REG_DWORD /d 1 /f >nul\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\LabConfig\" /v \"BypassCPUCheck\" /t REG_DWORD /d 1 /f >nul\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\LabConfig\" /v \"BypassStorageCheck\" /t REG_DWORD /d 1 /f >nul\r\n"
                    "reg add \"HKLM\\SYSTEM\\Setup\\MoSetup\" /v \"AllowUpgradesWithUnsupportedTPMOrCPU\" /t REG_DWORD /d 1 /f >nul\r\n"
                    "echo [+] Checking for unattended answer file...\r\n"
                    "set \"UNATTEND_PARAM=\"\r\n"
                    "for %%F in (\"%DRIVE%:\\*.xml\") do (\r\n"
                    "    if not defined UNATTEND_PARAM (\r\n"
                    "        set \"UNATTEND_PARAM=/unattend:%%F\"\r\n"
                    "        echo [+] Answer file: %%F\r\n"
                    "    )\r\n)\r\n"
                    "if defined UNATTEND_PARAM (\r\n"
                    "    echo [+] Launching Windows Setup with answer file, please wait...\r\n"
                    "    %DRIVE%:\\setup.exe %UNATTEND_PARAM%\r\n"
                    ") else (\r\n"
                    "    echo [+] Launching Windows Setup, please wait...\r\n"
                    "    %DRIVE%:\\setup.exe\r\n)\r\n"
                    "echo.\r\necho [+] Setup exited. Type EXIT to reboot.\r\ncmd /k\r\n"
                )

            with open(os.path.join(cmd_dir, 'WinSetup.cmd'), 'w', encoding='utf-8') as cf:
                cf.write(winsetup)

            # ── winpeshl.ini ──────────────────────────────────────────────────
            with open(os.path.join(cmd_dir, 'winpeshl.ini'), 'w', encoding='utf-8') as wf:
                wf.write('[LaunchApps]\r\n%SYSTEMDRIVE%\\Windows\\System32\\wpeinit.exe\r\n%SYSTEMDRIVE%\\Windows\\System32\\WinSetup.cmd\r\n')

            inject = (
                f"initrd ${{boot-url}}/Tools/MS/dynamic/{safe_id}/WinSetup.cmd WinSetup.cmd\n"
                f"initrd ${{boot-url}}/Tools/MS/dynamic/{safe_id}/ipxe.cfg ipxe.cfg\n"
                f"initrd ${{boot-url}}/Tools/MS/dynamic/{safe_id}/winpeshl.ini winpeshl.ini\n"
            )

            if is_setup:
                # ISO_WIN: boot.wim pxe/ISO/Windows/<name>/boot.wim altında
                wim_path     = f"/ISO/Windows/{f['name']}/boot.wim"
                local_wim    = os.path.join(ISO_WIN_DIR, f['name'], 'boot.wim')
                if not os.path.exists(local_wim):
                    menu_lines.append(f"item --gap \t\t{f['alias']} (extracting...)")
                    continue
                boot_lines.append(f":{item_id}\niseq ${{platform}} efi && goto {item_id}_efi || goto {item_id}_pcbios\n")
                boot_lines.append(
                    f":{item_id}_efi\nkernel ${{boot-url}}/Tools/MS/wimboot\n"
                    f"{inject}"
                    f"initrd ${{boot-url}}/Tools/MS/efi/microsoft/boot/bcd bcd\n"
                    f"initrd ${{boot-url}}/Tools/MS/boot.sdi boot.sdi\n"
                    f"initrd ${{boot-url}}{wim_path} boot.wim\n"
                    f"boot || goto menu_loop\n"
                )
                boot_lines.append(
                    f":{item_id}_pcbios\nkernel ${{boot-url}}/Tools/MS/wimboot rawbcd\n"
                    f"{inject}"
                    f"initrd ${{boot-url}}/Tools/MS/boot/bcd bcd\n"
                    f"initrd ${{boot-url}}/Tools/MS/bootmgr.exe bootmgr.exe\n"
                    f"initrd ${{boot-url}}/Tools/MS/boot.sdi boot.sdi\n"
                    f"initrd ${{boot-url}}{wim_path} boot.wim\n"
                    f"boot || goto menu_loop\n"
                )
            # WIM_MODIFIED: alt WIM'leri wim_entries.json'dan oku ve boot bloğu oluştur
            if not is_setup:
                folder_path      = os.path.join(WIM_DIR, f['name'])
                wim_entries_path = os.path.join(folder_path, 'wim_entries.json')
                wim_entries = []
                if os.path.exists(wim_entries_path):
                    try:
                        with open(wim_entries_path, 'r', encoding='utf-8') as wf:
                            data = json.load(wf)
                            wim_entries = data if isinstance(data, list) else [data]
                    except Exception:
                        pass
                if not wim_entries:
                    for sub in os.listdir(folder_path) if os.path.exists(folder_path) else []:
                        sub_path = os.path.join(folder_path, sub)
                        if os.path.isdir(sub_path) and os.path.exists(os.path.join(sub_path, 'boot.wim')):
                            wim_entries.append({'folder': sub, 'alias': sub})

                for wim in wim_entries:
                    wim_folder = wim.get('folder', '')
                    wim_alias  = wim.get('alias', wim_folder)
                    wim_safe   = wim_folder.replace('.', '_').replace(' ', '_')
                    wim_id     = f"boot_wim_mod_{safe_id}_{wim_safe}"
                    wim_base   = f"/WINPE/{f['name']}/{wim_folder}"
                    local_base = os.path.join(WIM_DIR, f['name'], wim_folder)
                    sdi_url = (f"${{boot-url}}{wim_base}/boot.sdi"
                               if os.path.exists(os.path.join(local_base, 'boot.sdi'))
                               else f"${{boot-url}}/Tools/MS/boot.sdi")
                    efi_mgr_url = (f"${{boot-url}}{wim_base}/bootmgfw.efi"
                                   if os.path.exists(os.path.join(local_base, 'bootmgfw.efi'))
                                   else f"${{boot-url}}/Tools/MS/efi/microsoft/boot/bootmgfw.efi")
                    boot_lines.append(f":{wim_id}\niseq ${{platform}} efi && goto {wim_id}_efi || goto {wim_id}_pcbios\n")
                    boot_lines.append(
                        f":{wim_id}_efi\n"
                        f"kernel ${{boot-url}}/Tools/MS/wimboot\n"
                        f"{inject}"
                        f"initrd ${{boot-url}}/Tools/MS/efi/microsoft/boot/bcd bcd\n"
                        f"initrd {efi_mgr_url} bootmgfw.efi\n"
                        f"initrd {sdi_url} boot.sdi\n"
                        f"initrd ${{boot-url}}{wim_base}/boot.wim boot.wim\n"
                        f"boot || goto menu_loop\n"
                    )
                    boot_lines.append(
                        f":{wim_id}_pcbios\n"
                        f"kernel ${{boot-url}}/Tools/MS/wimboot rawbcd\n"
                        f"{inject}"
                        f"initrd ${{boot-url}}/Tools/MS/boot/bcd bcd\n"
                        f"initrd ${{boot-url}}/Tools/MS/bootmgr.exe bootmgr.exe\n"
                        f"initrd {sdi_url} boot.sdi\n"
                        f"initrd ${{boot-url}}{wim_base}/boot.wim boot.wim\n"
                        f"boot || goto menu_loop\n"
                    )
            
        elif f['type'] == 'ISO_LINUX':
            if f.get('is_dir'):
                iso_folder   = f['name']
                iso_file     = f.get('iso_file', '')
                vmlinuz_path = f"/ISO/Linux/{iso_folder}/vmlinuz"
                initrd_path  = f"/ISO/Linux/{iso_folder}/initrd.img"
                
                # Parse domain and port for Linux initramfs which might lack DNS
                domain_clean = domain.split(':')[0] if ':' in domain else domain
                port = domain.split(':')[1] if ':' in domain else '8080'
                try:
                    _uip = socket.gethostbyname(domain_clean)
                except Exception:
                    _uip = domain_clean
                
                # Distro tespiti
                hint_path = os.path.join(ISO_LIN_DIR, iso_folder, 'distro_hint.txt')
                distro_type = "generic"
                if os.path.exists(hint_path):
                    try:
                        with open(hint_path, 'rb') as hf:
                            raw = hf.read().strip()
                            if raw.startswith(b'\xef\xbb\xbf'): raw = raw[3:]
                            distro_type = raw.decode('utf-8', errors='ignore').strip().lower()
                    except: pass
                lower_name = (iso_folder + iso_file).lower()
                if distro_type == "generic":
                    if any(k in lower_name for k in ['ubuntu','mint','pop','zorin','elementary']): distro_type = "ubuntu"
                    elif any(k in lower_name for k in ['debian','kali','mx','parrot']): distro_type = "debian"
                    elif any(k in lower_name for k in ['fedora']): distro_type = "fedora"
                    elif any(k in lower_name for k in ['rocky','alma','centos','rhel']): distro_type = "rhel"
                    elif any(k in lower_name for k in ['opensuse','suse']): distro_type = "opensuse"
                    elif any(k in lower_name for k in ['arch','endeavour']): distro_type = "arch"
                    elif 'manjaro' in lower_name: distro_type = "manjaro"
                    elif 'alpine' in lower_name: distro_type = "alpine"

                # Boot argümanları
                if distro_type == "ubuntu":
                    # Tüm Ubuntu sürümleri için tam ISO indirme (url= modu)
                    iso_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{iso_file}"
                    boot_lines.append(
                        f":{item_id}\n"
                        f"kernel ${{boot-url}}{vmlinuz_path}\n"
                        f"initrd ${{boot-url}}{initrd_path}\n"
                        f"imgargs vmlinuz initrd=initrd.img boot=casper ip=dhcp url={iso_url} cloud-init=disabled quiet splash\n"
                        f"boot || goto menu_loop\n"
                    )
                    continue
                elif distro_type == "debian":
                    sqfs_hint = os.path.join(ISO_LIN_DIR, iso_folder, 'squashfs_path.txt')
                    sqfs_rel  = open(sqfs_hint, encoding='utf-8-sig').read().strip() if os.path.exists(sqfs_hint) else 'live/filesystem.squashfs'
                    squashfs_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{sqfs_rel}"
                    args = f"initrd=initrd.img boot=live components ip=dhcp fetch={squashfs_url} quiet splash"
                elif distro_type in ("fedora", "rhel", "void"):
                    sqfs_hint = os.path.join(ISO_LIN_DIR, iso_folder, 'squashfs_path.txt')
                    sqfs_rel  = open(sqfs_hint, encoding='utf-8-sig').read().strip() if os.path.exists(sqfs_hint) else 'LiveOS/squashfs.img'
                    squashfs_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{sqfs_rel}"
                    args = f"initrd=initrd.img ip=dhcp root=live:{squashfs_url} rd.live.image rd.neednet=1 rd.lvm=0 rd.luks=0 quiet"
                elif distro_type == "opensuse":
                    boot_mode_f = os.path.join(ISO_LIN_DIR, iso_folder, 'boot_mode.txt')
                    boot_mode   = open(boot_mode_f, encoding='utf-8-sig').read().strip() if os.path.exists(boot_mode_f) else 'live'
                    if boot_mode == 'installer':
                        args = f"initrd=initrd.img ip=dhcp install=http://{_uip}:{port}/ISO/Linux/{iso_folder}/ quiet"
                    else:
                        sqfs_hint = os.path.join(ISO_LIN_DIR, iso_folder, 'squashfs_path.txt')
                        sqfs_rel  = open(sqfs_hint, encoding='utf-8-sig').read().strip() if os.path.exists(sqfs_hint) else 'LiveOS/squashfs.img'
                        squashfs_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{sqfs_rel}"
                        args = f"initrd=initrd.img ip=dhcp root=live:{squashfs_url} rd.live.image rd.neednet=1 quiet splash"
                elif distro_type == "nixos":
                    init_f   = os.path.join(ISO_LIN_DIR, iso_folder, 'nixos_init.txt')
                    syscfg_f = os.path.join(ISO_LIN_DIR, iso_folder, 'nixos_syscfg.txt')
                    init_path   = open(init_f, encoding='utf-8-sig').read().strip()   if os.path.exists(init_f)   else ''
                    syscfg_path = open(syscfg_f, encoding='utf-8-sig').read().strip() if os.path.exists(syscfg_f) else ''
                    if init_path:
                        extra = f" systemConfig={syscfg_path}" if syscfg_path else ""
                        args = f"initrd=initrd.img ip=dhcp init={init_path}{extra}"
                    else:
                        iso_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{iso_file}"
                        args = f"initrd=initrd.img ip=dhcp root=live:{iso_url} rd.live.image rd.neednet=1 quiet"
                elif distro_type == "arch":
                    args = f"initrd=initrd.img ip=dhcp archisobasedir=arch archiso_http_srv=http://{_uip}:{port}/ISO/Linux/{iso_folder}/ quiet"
                elif distro_type == "manjaro":
                    args = f"initrd=initrd.img ip=dhcp misobasedir=manjaro img_loop=manjaro/x86_64/airootfs.sfs archiso_http_srv=http://{_uip}:{port}/ISO/Linux/{iso_folder}/ quiet splash"
                elif distro_type == "alpine":
                    args = f"initrd=initrd.img ip=dhcp modloop=http://{_uip}:{port}/ISO/Linux/{iso_folder}/boot/modloop-lts quiet"
                else:
                    sqfs_hint = os.path.join(ISO_LIN_DIR, iso_folder, 'squashfs_path.txt')
                    if os.path.exists(sqfs_hint):
                        sqfs_rel = open(sqfs_hint, encoding='utf-8-sig').read().strip()
                        squashfs_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{sqfs_rel}"
                        args = f"initrd=initrd.img ip=dhcp root=live:{squashfs_url} rd.live.image rd.neednet=1 quiet"
                    else:
                        iso_url = f"http://{_uip}:{port}/ISO/Linux/{iso_folder}/{iso_file}"
                        args = f"initrd=initrd.img ip=dhcp root=live:{iso_url} rd.live.image rd.neednet=1 quiet"

                # EFI ve BIOS için aynı yöntem: kernel + initrd
                boot_lines.append(
                    f":{item_id}\n"
                    f"kernel ${{boot-url}}{vmlinuz_path} {args}\n"
                    f"initrd ${{boot-url}}{initrd_path}\n"
                    f"boot || goto menu_loop\n"
                )
        elif f['type'] == 'WIM':
            path = f"/WINPE/{f['name']}/boot.wim"
            boot_lines.append(f":{item_id}\niseq ${{platform}} efi && goto {item_id}_efi || goto {item_id}_pcbios\n")
            boot_lines.append(f":{item_id}_efi\nset path_file {path}\nkernel ${{boot-url}}/Tools/MS/wimboot\ninitrd ${{boot-url}}/Tools/MS/efi/microsoft/boot/bcd\ninitrd ${{boot-url}}/Tools/MS/boot.sdi\ninitrd ${{boot-url}}${{path_file}}\nboot || goto menu_loop\n")
            boot_lines.append(f":{item_id}_pcbios\nset path_file {path}\nkernel ${{boot-url}}/Tools/MS/wimboot rawbcd\ninitrd ${{boot-url}}/Tools/MS/boot/bcd bcd\ninitrd ${{boot-url}}/Tools/MS/bootmgr.exe bootmgr.exe\ninitrd ${{boot-url}}/Tools/MS/boot.sdi boot.sdi\ninitrd ${{boot-url}}${{path_file}} boot.wim\nboot || goto menu_loop\n")


    template_path = os.path.join(PXE_DIR, 'autoexec.ipxe')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f: content = f.read()
        content = re.sub(r'set boot_domain .*', f'set boot_domain {domain}', content)
        content = re.sub(r'set boot-url .*', r'set boot-url http://${boot_domain}', content)
        content = re.sub(
            r'choose --default \S+ --timeout \d+ target && goto \$\{target\}',
            f'choose --default {default_boot} --timeout {timeout_ms} target && goto ${{target}}',
            content
        )
        content = re.sub(r'# --- DYNAMIC MENU START ---.*?# --- DYNAMIC MENU END ---', f'# --- DYNAMIC MENU START ---\n' + '\n'.join(menu_lines) + '\n# --- DYNAMIC MENU END ---', content, flags=re.DOTALL)
        content = re.sub(r'# --- DYNAMIC BOOT START ---.*?# --- DYNAMIC BOOT END ---', f'# --- DYNAMIC BOOT START ---\n' + '\n'.join(boot_lines) + '\n# --- DYNAMIC BOOT END ---', content, flags=re.DOTALL)
        with open(template_path, 'w', encoding='utf-8') as f: f.write(content)

# ─── Auth & Security ────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        settings = _load_app_settings()
        pwd_hash = settings.get('admin_password_hash')
        if pwd_hash and not session.get('logged_in'):
            return jsonify({'success': False, 'error': 'Unauthorized', 'needs_login': True}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/auth/status')
def auth_status():
    settings = _load_app_settings()
    has_pwd = bool(settings.get('admin_password_hash'))
    logged_in = session.get('logged_in', False)
    return jsonify({'has_password': has_pwd, 'logged_in': logged_in})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    settings = _load_app_settings()
    pwd_hash = settings.get('admin_password_hash')
    if not pwd_hash:
        return jsonify({'success': True})
    if username == 'admin' and check_password_hash(pwd_hash, password):
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'login_error'})

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.pop('logged_in', None)
    return jsonify({'success': True})

@app.route('/api/auth/set_password', methods=['POST'])
@login_required
def auth_set_password():
    data = request.json
    new_pwd = data.get('new_password')
    current_pwd = data.get('current_password')
    settings = _load_app_settings()
    pwd_hash = settings.get('admin_password_hash')
    
    if pwd_hash: # update mode
        if not check_password_hash(pwd_hash, current_pwd):
            return jsonify({'success': False, 'error': 'msg_pwd_error'})
            
    if new_pwd:
        settings['admin_password_hash'] = generate_password_hash(new_pwd)
        session['logged_in'] = True
    else:
        settings.pop('admin_password_hash', None)
        session.pop('logged_in', None)
        
    with open(os.path.join(PXE_DIR, 'app_settings.json'), 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)
    return jsonify({'success': True})

@app.route('/api/service/status')
def service_status():
    try:
        subprocess.check_output(
            ['schtasks', '/query', '/tn', 'PXE_Server'], 
            stderr=subprocess.STDOUT, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return jsonify({'installed': True})
    except:
        return jsonify({'installed': False})

@app.route('/api/service/install', methods=['POST'])
@login_required
def service_install():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return jsonify({'success': False, 'error': 'msg_service_error'})
    try:
        exe_path = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)
        cmd = ['schtasks', '/create', '/tn', 'PXE_Server', '/tr', f'"{exe_path}" --headless', '/sc', 'onstart', '/ru', 'SYSTEM', '/rl', 'HIGHEST', '/f']
        subprocess.check_call(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/service/remove', methods=['POST'])
@login_required
def service_remove():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return jsonify({'success': False, 'error': 'msg_service_error'})
    try:
        subprocess.check_call(
            ['schtasks', '/delete', '/tn', 'PXE_Server', '/f'], 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/')
def index(): return send_from_directory(BASE_DIR, 'index.html')

@app.route('/ISO/Windows/<folder>/<filename>')
def serve_iso_win_file(folder, filename):
    """Windows ISO dosyasını HTTP üzerinden serve eder."""
    _mark_active(request.remote_addr)
    file_path = os.path.join(ISO_WIN_DIR, folder, filename)
    if os.path.isfile(file_path):
        return _serve_ranged_file(file_path)
    return Response('Not Found', status=404)

@app.route('/ISO/Windows/<path:filename>')
def serve_iso_win(filename): _mark_active(request.remote_addr); return send_from_directory(ISO_WIN_DIR, filename)

def _serve_ranged_file(full_path):
    """Büyük dosyaları Range-request desteğiyle serve eder (squashfs için şart)."""
    size   = os.path.getsize(full_path)
    rng    = request.headers.get('Range', '')
    s, e_  = 0, size - 1
    status = 200
    if rng.startswith('bytes='):
        try:
            r  = rng[6:].split('-')
            s  = int(r[0]) if r[0] else size - int(r[1])
            e_ = int(r[1]) if r[1] else size - 1
            status = 206
        except Exception:
            pass
    length = e_ - s + 1
    def _gen():
        with open(full_path, 'rb') as fh:
            fh.seek(s); rem = length
            while rem > 0:
                chunk = fh.read(min(65536, rem))
                if not chunk: break
                rem -= len(chunk); yield chunk
    hdrs = {
        'Content-Length': str(length),
        'Content-Type':   'application/octet-stream',
        'Accept-Ranges':  'bytes',
    }
    if status == 206:
        hdrs['Content-Range'] = f'bytes {s}-{e_}/{size}'
    return Response(stream_with_context(_gen()), status=status, headers=hdrs)

@app.route('/ISO/Linux/')
@app.route('/ISO/Linux')
def serve_iso_lin_root():
    folders = sorted(e for e in os.listdir(ISO_LIN_DIR) if os.path.isdir(os.path.join(ISO_LIN_DIR, e))) if os.path.exists(ISO_LIN_DIR) else []
    rows = ''.join(
        f'<tr><td>📁 <a href="/ISO/Linux/{e}/">{e}</a></td>'
        f'<td style="text-align:right;padding-left:40px;color:#888"></td></tr>'
        for e in folders)
    html = (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<title>Linux ISOs — iPXE Manager</title>'
        f'<style>body{{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:30px;max-width:900px;margin:0 auto}}'
        f'a{{color:#4ec9b0;text-decoration:none}}a:hover{{text-decoration:underline}}'
        f'table{{border-collapse:collapse;width:100%}}'
        f'td{{padding:4px 8px;border-bottom:1px solid #333}}'
        f'h1{{color:#4ec9b0;font-size:1.1rem;margin:0 0 4px 0;letter-spacing:2px}}'
        f'h2{{color:#9cdcfe;margin:20px 0 6px 0}}'
        f'.footer{{margin-top:50px;text-align:center;color:#555;font-size:0.8rem;border-top:1px solid #2a2a2a;padding-top:18px}}'
        f'</style></head>'
        f'<body>'
        f'<h1>⚡ iPXE Manager</h1>'
        f'<hr style="border:none;border-top:1px solid #2a2a2a;margin:8px 0 24px 0">'
        f'<h2>🐧 Linux ISO Browser</h2>'
        f'<table>{rows}</table>'
        f'<div class="footer">'
        f'made by <strong style="color:#4ec9b0"><a href="https://buymeacoffee.com/abdullaherturk" target="_blank" style="color:#4ec9b0; text-decoration:none;">Abdullah ERTÜRK</a></strong><br><br>'
        f'<a href="https://github.com/abdullah-erturk">github.com/abdullah-erturk</a>'
        f' &nbsp;|&nbsp; '
        f'<a href="https://erturk-dev.netlify.app">erturk-dev.netlify.app</a>'
        f'</div>'
        f'</body></html>')
    return Response(html, status=200, headers={'Content-Type': 'text/html;charset=utf-8'})

@app.route('/ISO/Linux/<folder>/')
@app.route('/ISO/Linux/<folder>')
def serve_iso_lin_dir(folder):
    drv = _ensure_iso_mounted(folder)
    if drv:
        root = f"{drv}:\\"
        try:
            entries = sorted(os.listdir(root))
        except Exception:
            entries = []
        rows = f'<tr><td colspan="2"><a href="/ISO/Linux/">⬆ ..</a></td></tr>'
        for e in entries:
            ep  = os.path.join(root, e)
            eis = os.path.isdir(ep)
            href = f'/ISO/Linux/{folder}/{e}' + ('/' if eis else '')
            sz   = '—' if eis else f'{os.path.getsize(ep):,} B'
            rows += (f'<tr><td>{"📁" if eis else "📄"} <a href="{href}">{e}</a></td>'
                     f'<td style="text-align:right;padding-left:40px;color:#888">{sz}</td></tr>')
        html = (
            f'<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<title>{folder} — ISO Browser | iPXE Manager</title>'
            f'<style>body{{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:30px;max-width:900px;margin:0 auto}}'
            f'a{{color:#4ec9b0;text-decoration:none}}a:hover{{text-decoration:underline}}'
            f'table{{border-collapse:collapse;width:100%}}'
            f'td{{padding:4px 8px;border-bottom:1px solid #333}}'
            f'h1{{color:#4ec9b0;font-size:1.1rem;margin:0 0 4px 0;letter-spacing:2px}}'
            f'h2{{color:#9cdcfe;margin:20px 0 6px 0}}'
            f'.crumbs{{margin-bottom:20px;font-size:0.9rem;color:#888}}'
            f'.footer{{margin-top:50px;text-align:center;color:#555;font-size:0.8rem;border-top:1px solid #2a2a2a;padding-top:18px}}'
            f'</style></head>'
            f'<body>'
            f'<h1>⚡ iPXE Manager</h1>'
            f'<hr style="border:none;border-top:1px solid #2a2a2a;margin:8px 0 24px 0">'
            f'<h2>🐧 Linux ISO Browser</h2>'
            f'<div class="crumbs"><a href="/ISO/Linux/">Linux ISOs</a> / {folder}</div>'
            f'<table>{rows}</table>'
            f'<div class="footer">'
            f'made by <strong style="color:#4ec9b0"><a href="https://buymeacoffee.com/abdullaherturk" target="_blank" style="color:#4ec9b0; text-decoration:none;">Abdullah ERTÜRK</a></strong><br><br>'
            f'<a href="https://github.com/abdullah-erturk">github.com/abdullah-erturk</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="https://erturk-dev.netlify.app">erturk-dev.netlify.app</a>'
            f'</div>'
            f'</body></html>')
        return Response(html, status=200, headers={'Content-Type': 'text/html;charset=utf-8'})
    return Response(f'ISO could not be mounted: {folder}', status=503, mimetype='text/plain')

@app.route('/ISO/Linux/<path:filename>')
def serve_iso_lin(filename):
    _mark_active(request.remote_addr)
    full = os.path.join(ISO_LIN_DIR, filename)
    if os.path.isfile(full):
        return send_from_directory(ISO_LIN_DIR, filename)
    parts = filename.replace('\\', '/').split('/')
    if len(parts) < 2:
        return Response('Not Found', status=404)
    folder     = parts[0]
    inner_path = '/'.join(parts[1:])
    iso_path   = _find_iso_path(folder)
    if not iso_path:
        return Response(f'[iPXE] ISO folder not found: {folder}', status=404, mimetype='text/plain')
    drv = _ensure_iso_mounted(folder)
    if not drv:
        err_log = ''
        try:
            log_p = os.path.join(os.path.dirname(iso_path), 'mount_error.log')
            if os.path.exists(log_p):
                err_log = open(log_p, encoding='utf-8', errors='replace').read()
        except Exception:
            pass
        return Response(
            f'[iPXE] ISO could not be mounted: {iso_path}\n\nmount_error.log:\n{err_log or "(no log)"}',
            status=503, mimetype='text/plain')
    # vmlinuz / initrd.img icin hint dosyasi varsa gercek ISO yolunu kullan
    iso_inner = inner_path
    if inner_path in ('vmlinuz', 'initrd.img'):
        hint_key  = 'kernel_path.txt' if inner_path == 'vmlinuz' else 'initrd_path.txt'
        hint_file = os.path.join(ISO_LIN_DIR, folder, hint_key)
        if os.path.exists(hint_file):
            try:
                hinted = open(hint_file, encoding='utf-8', errors='replace').read().strip()
                if hinted:
                    iso_inner = hinted
            except Exception:
                pass

    iso_file = os.path.join(f"{drv}:\\", iso_inner.replace('/', os.sep))
    if os.path.isdir(iso_file):
        # Alt dizin browse isteği — listing döndür
        try:
            entries = sorted(os.listdir(iso_file))
        except Exception:
            entries = []
        # Breadcrumb oluştur
        parts_bc = [p for p in inner_path.strip('/').split('/') if p]
        crumbs = f'<a href="/ISO/Linux/">Linux ISOs</a> / <a href="/ISO/Linux/{folder}/">{folder}</a>'
        cp = f'/ISO/Linux/{folder}/'
        for part in parts_bc:
            cp += part + '/'
            crumbs += f' / <a href="{cp}">{part}</a>'
        parent_parts = parts_bc[:-1]
        parent = f'/ISO/Linux/{folder}/' + '/'.join(parent_parts) + ('/' if parent_parts else '')
        rows = f'<tr><td colspan="2"><a href="{parent}">⬆ ..</a></td></tr>'
        for e in entries:
            ep  = os.path.join(iso_file, e)
            eis = os.path.isdir(ep)
            href = f'/ISO/Linux/{folder}/{inner_path.rstrip("/")}/{e}' + ('/' if eis else '')
            sz   = '—' if eis else f'{os.path.getsize(ep):,} B'
            rows += (f'<tr><td>{"📁" if eis else "📄"} <a href="{href}">{e}</a></td>'
                     f'<td style="text-align:right;padding-left:40px;color:#888">{sz}</td></tr>')
        html = (
            f'<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<title>{inner_path} — ISO Browser | iPXE Manager</title>'
            f'<style>body{{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:30px;max-width:900px;margin:0 auto}}'
            f'a{{color:#4ec9b0;text-decoration:none}}a:hover{{text-decoration:underline}}'
            f'table{{border-collapse:collapse;width:100%}}'
            f'td{{padding:4px 8px;border-bottom:1px solid #333}}'
            f'h1{{color:#4ec9b0;font-size:1.1rem;margin:0 0 4px 0;letter-spacing:2px}}'
            f'h2{{color:#9cdcfe;margin:20px 0 6px 0}}'
            f'.crumbs{{margin-bottom:20px;font-size:0.9rem;color:#888}}'
            f'.footer{{margin-top:50px;text-align:center;color:#555;font-size:0.8rem;border-top:1px solid #2a2a2a;padding-top:18px}}'
            f'</style></head>'
            f'<body>'
            f'<h1>⚡ iPXE Manager</h1>'
            f'<hr style="border:none;border-top:1px solid #2a2a2a;margin:8px 0 24px 0">'
            f'<h2>🐧 Linux ISO Browser</h2>'
            f'<div class="crumbs">{crumbs}</div>'
            f'<table>{rows}</table>'
            f'<div class="footer">'
            f'made by <strong style="color:#4ec9b0"><a href="https://buymeacoffee.com/abdullaherturk" target="_blank" style="color:#4ec9b0; text-decoration:none;">Abdullah ERTÜRK</a></strong><br><br>'
            f'<a href="https://github.com/abdullah-erturk">github.com/abdullah-erturk</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="https://erturk-dev.netlify.app">erturk-dev.netlify.app</a>'
            f'</div>'
            f'</body></html>')
        return Response(html, status=200, headers={'Content-Type': 'text/html;charset=utf-8'})
    if os.path.isfile(iso_file):
        return _serve_ranged_file(iso_file)

    # Hint yoksa veya hinted yol da bulunamadıysa distro bazlı fallback tara
    if inner_path in ('vmlinuz', 'initrd.img'):
        patterns = (['vmlinuz','vmlinuz-linux','linux','bzImage']
                    if inner_path == 'vmlinuz'
                    else ['initrd.img','initrd','initramfs-linux.img','initrd.gz','initrd.lz'])
        search_dirs = ['images/pxeboot','boot/x86_64/loader','boot/x86_64',
                       'casper','live','arch/boot/x86_64','boot','isolinux']
        root = f"{drv}:\\"
        for sdir in search_dirs:
            for pat in patterns:
                candidate = os.path.join(root, sdir.replace('/', os.sep), pat)
                if os.path.isfile(candidate):
                    return _serve_ranged_file(candidate)

    # Hangi dosyalar var debug log
    try:
        log_p = os.path.join(os.path.dirname(iso_path), 'serve_debug.log')
        with open(log_p, 'w', encoding='utf-8') as lf:
            lf.write(f"Requested : {iso_file}\nDrive     : {drv}:\\\n\n")
            root = f"{drv}:\\"
            for base, dirs, fnames in os.walk(root):
                depth = base.replace(root, '').count(os.sep)
                if depth >= 2: dirs.clear(); continue
                indent = '  ' * depth
                lf.write(f"{indent}{os.path.basename(base) or drv}:\\\n")
                for fn in fnames[:30]:
                    lf.write(f"{indent}  {fn}\n")
    except Exception:
        pass
    return Response(
        f'[iPXE] File not found at mount point: {iso_file}\nDrive: {drv}:\\\n'
        f'Details: /api/linux_debug/{folder}',
        status=404, mimetype='text/plain')

@app.route('/api/linux_debug/<folder>')
@login_required
def linux_iso_debug(folder):
    result = {'folder': folder, 'iso_path': None, 'mounted': False,
              'drive': None, 'mount_error': None, 'files': []}
    iso_path = _find_iso_path(folder)
    if not iso_path:
        result['error'] = f'ISO not found: {os.path.join(ISO_LIN_DIR, folder)}'
        return jsonify(result)
    result['iso_path'] = iso_path
    for log_name in ('mount_error.log', 'serve_debug.log'):
        p = os.path.join(os.path.dirname(iso_path), log_name)
        if os.path.exists(p):
            try: result[log_name] = open(p, encoding='utf-8', errors='replace').read()
            except Exception: pass
    with _iso_mounts_lock:
        drv = _iso_mounts.get(folder)
    if drv and os.path.exists(f"{drv}:\\"):
        result['mounted'] = True
        result['drive']   = drv
        try:
            root  = f"{drv}:\\"
            files = []
            for base, dirs, fnames in os.walk(root):
                depth = base.replace(root, '').count(os.sep)
                if depth >= 3: dirs.clear(); continue
                for fn in fnames:
                    files.append(os.path.join(base, fn).replace(root, '').replace('\\', '/'))
            result['files'] = files[:200]
        except Exception as e:
            result['files_error'] = str(e)
    else:
        result['mounted'] = False
        drv2 = _ensure_iso_mounted(folder)
        result['remount_attempt'] = drv2 or 'FAILED'
    return jsonify(result)

@app.route('/Tools/grub/<path:filename>')
def serve_grub(filename): return send_from_directory(os.path.join(PXE_DIR, 'Tools', 'grub'), filename)

@app.route('/ubuntu/')
@app.route('/ubuntu/<path:filepath>')
def serve_ubuntu_iso(filepath=''):
    """Ubuntu ISO içeriğini mount noktasından serve eder — casper için."""
    # Ubuntu klasörünü bul
    ubuntu_folder = None
    if os.path.exists(ISO_LIN_DIR):
        for entry in os.listdir(ISO_LIN_DIR):
            hint = os.path.join(ISO_LIN_DIR, entry, 'distro_hint.txt')
            if os.path.exists(hint):
                try:
                    with open(hint, 'rb') as hf:
                        raw = hf.read().strip()
                        if raw.startswith(b'\xef\xbb\xbf'): raw = raw[3:]
                        if raw.decode('utf-8', errors='ignore').strip().lower() == 'ubuntu':
                            ubuntu_folder = entry
                            break
                except: pass
            if not ubuntu_folder and 'ubuntu' in entry.lower():
                ubuntu_folder = entry

    if not ubuntu_folder:
        return Response('Ubuntu ISO not found', status=404)

    drv = _ensure_iso_mounted(ubuntu_folder)
    if not drv:
        return Response('Ubuntu ISO not mounted', status=503)

    root = f"{drv}:\\"
    if filepath:
        full_path = os.path.join(root, filepath.replace('/', os.sep))
        if os.path.isfile(full_path):
            return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))
        return Response('Not found', status=404)
    # Dizin listesi
    return Response('Ubuntu ISO mounted', status=200)

@app.route('/autoinstall/')
@app.route('/autoinstall')
def serve_autoinstall_dir():
    """autoinstall dizin isteği — user-data ve meta-data listesi."""
    return Response('user-data\nmeta-data\n', mimetype='text/plain')

@app.route('/autoinstall/user-data')
def serve_user_data():
    """Minimal Ubuntu autoinstall user-data."""
    content = (
        "#cloud-config\n"
        "autoinstall:\n"
        "  version: 1\n"
        "  apt:\n"
        "    fallback: offline\n"
        "    preserve_sources_list: false\n"
        "  shutdown: reboot\n"
    )
    return Response(content, mimetype='text/yaml')

@app.route('/autoinstall/meta-data')
def serve_meta_data():
    """Ubuntu autoinstall meta-data (boş olabilir)."""
    return Response('instance-id: ubuntu-pxe\nlocal-hostname: ubuntu-pxe\n', mimetype='text/yaml')


# ─── ISO MOUNT YÖNETİMİ ──────────────────────────────────────────────────────

_iso_mounts      = {}   # {folder: drive_letter}
_iso_mounts_lock = threading.Lock()

def _find_iso_path(folder):
    """Klasör adından ISO dosyasını bulur (WIM_MODIFIED, ISO_WIN veya ISO_LINUX)."""
    # WIM_MODIFIED
    wim_folder = os.path.join(WIM_DIR, folder)
    if os.path.isdir(wim_folder):
        p = os.path.join(wim_folder, 'source.iso')
        if os.path.exists(p): return p
        for f in os.listdir(wim_folder):
            if f.lower().endswith('.iso'):
                return os.path.join(wim_folder, f)
    # ISO_WIN
    win_folder = os.path.join(ISO_WIN_DIR, folder)
    if os.path.isdir(win_folder):
        p = os.path.join(win_folder, 'source.iso')
        if os.path.exists(p): return p
        for f in os.listdir(win_folder):
            if f.lower().endswith('.iso'):
                return os.path.join(win_folder, f)
    # ISO_LINUX
    lin_folder = os.path.join(ISO_LIN_DIR, folder)
    if os.path.isdir(lin_folder):
        for f in os.listdir(lin_folder):
            if f.lower().endswith('.iso'):
                return os.path.join(lin_folder, f)
    return None

_iso_exclusions = set()  # Eklenen Defender exclusion yolları

def _defender_exclude(path):
    """Windows Defender dışlama listesine ekler."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
             f"Add-MpPreference -ExclusionPath '{path}' -ErrorAction SilentlyContinue"],
            startupinfo=si, timeout=10)
        _iso_exclusions.add(path)
    except Exception:
        pass

def _defender_remove_exclude(path):
    """Windows Defender dışlama listesinden kaldırır."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
             f"Remove-MpPreference -ExclusionPath '{path}' -ErrorAction SilentlyContinue"],
            startupinfo=si, timeout=10)
        _iso_exclusions.discard(path)
    except Exception:
        pass

def _defender_remove_all():
    """Tüm eklenen Defender exclusion'larını kaldırır."""
    for path in list(_iso_exclusions):
        _defender_remove_exclude(path)

def _mount_iso(folder):
    """ISO'yu mount eder, sürücü harfini döner."""
    iso_path = _find_iso_path(folder)
    if not iso_path: return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE

    # Defender mount oncesi devre disi birakilir
    _defender_exclude(iso_path)
    _defender_exclude(os.path.dirname(iso_path))

    # --- Yöntem 1: Zaten mount edilmiş mi kontrol et (Dismount yapmadan önce) ---
    try:
        rc = subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
             f"$d=Get-DiskImage -ImagePath '{iso_path}' -EA SilentlyContinue; "
             f"if($d -and $d.Attached){{($d|Get-Volume).DriveLetter}}else{{''}}"],
            capture_output=True, text=True, startupinfo=si, timeout=15)
        existing = rc.stdout.strip()
        if existing and len(existing) == 1 and existing.isalpha():
            _defender_exclude(f"{existing}:\\")
            _defender_exclude(iso_path)
            return existing
    except Exception:
        pass

    # --- Yöntem 2: Mount + multi-fallback drive letter detection ---
    try:
        # Önce olası kalıntı mount'u temizle
        subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
             f"Dismount-DiskImage -ImagePath '{iso_path}' -EA SilentlyContinue | Out-Null"],
            startupinfo=si, timeout=15)
        time.sleep(1.0)  # Drive letter serbest bırakılana kadar bekle

        # Mount + 30 iterasyon * 500ms = 15s polling + 2 katmanlı Get-DiskImage fallback
        r = subprocess.run(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
             f"$m = Mount-DiskImage -ImagePath '{iso_path}' -PassThru -EA SilentlyContinue; "
             f"$drv = ''; "
             f"for($i=0; $i -lt 30; $i++) {{ "
             f"  if ($m) {{ $drv = ($m | Get-Volume -EA SilentlyContinue).DriveLetter; if ($drv) {{ break }} }} "
             f"  Start-Sleep -Milliseconds 500 "
             f"}}; "
             f"if (-not $drv) {{ "
             f"  $di = Get-DiskImage -ImagePath '{iso_path}' -EA SilentlyContinue; "
             f"  if ($di -and $di.Attached) {{ $drv = ($di | Get-Volume -EA SilentlyContinue).DriveLetter }} "
             f"}}; "
             f"if (-not $drv) {{ "
             f"  $di = Get-DiskImage -ImagePath '{iso_path}' -EA SilentlyContinue; "
             f"  if ($di -and $di.Attached) {{ $drv = ($di | Get-Disk -EA SilentlyContinue | Get-Partition -EA SilentlyContinue | Get-Volume -EA SilentlyContinue).DriveLetter | Select-Object -First 1 }} "
             f"}}; "
             f"$drv"],
            capture_output=True, text=True, startupinfo=si, timeout=90)
        drv = r.stdout.strip()
        if drv and len(drv) == 1 and drv.isalpha():
            _defender_exclude(f"{drv}:\\")
            _defender_exclude(iso_path)
            return drv

        # Yontem 2 basarisiz: hata logla
        try:
            with open(os.path.join(os.path.dirname(iso_path), 'mount_error.log'), 'w') as ef:
                ef.write(f"stdout:{r.stdout}\nstderr:{r.stderr}\n")
        except Exception: pass
    except Exception as e:
        try:
            with open(os.path.join(os.path.dirname(iso_path), 'mount_error.log'), 'w') as ef:
                ef.write(f"Exception:{e}\n")
        except Exception: pass

    return None

def _ensure_iso_mounted(folder):
    with _iso_mounts_lock:
        if folder in _iso_mounts:
            drv = _iso_mounts[folder]
            if drv and os.path.exists(f"{drv}:\\"): return drv
            _iso_mounts.pop(folder, None)
    # Mount islemi LOCK DISINDA (60 sn surabilir, diger thread'leri bloklamaz)
    drv = _mount_iso(folder)
    with _iso_mounts_lock:
        if drv: _iso_mounts[folder] = drv
        else: _iso_mounts.pop(folder, None)
    return drv

def _unmount_iso(folder):
    """Tek bir ISO'yu unmount eder ve Defender exclusion'ını temizler."""
    with _iso_mounts_lock: drv = _iso_mounts.get(folder)
    if drv: _defender_remove_exclude(f"{drv}:\\")
    iso_path = _find_iso_path(folder)
    if iso_path:
        _defender_remove_exclude(iso_path)
        _defender_remove_exclude(os.path.dirname(iso_path))
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            subprocess.run(['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
                 f"Dismount-DiskImage -ImagePath '{iso_path}' -EA SilentlyContinue | Out-Null"],
                startupinfo=si, timeout=15)
        except Exception: pass
    with _iso_mounts_lock: _iso_mounts.pop(folder, None)

def _unmount_all_isos():
    """Tüm mount edilmiş ISO'ları unmount eder ve Defender exclusion'larını kaldırır."""
    try:
        # 1. Kayıtlı olanları temizle
        with _iso_mounts_lock:
            folders = list(_iso_mounts.keys())
        for folder in folders:
            _unmount_iso(folder)
            
        # 2. Agresif temizlik (hafızada olmayan ama klasörde bulunan tüm ISO'lar için)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        ps_cmd = (
            f"$dirs = @('{WIM_DIR}', '{ISO_WIN_DIR}', '{ISO_LIN_DIR}'); "
            "foreach($d in $dirs) { if(Test-Path $d) { Get-ChildItem -Path $d -Recurse -Filter '*.iso' | ForEach-Object { "
            "Dismount-DiskImage -ImagePath $_.FullName -ErrorAction SilentlyContinue | Out-Null "
            "} } }"
        )
        subprocess.run(['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps_cmd], startupinfo=si, timeout=30)
    except Exception:
        pass
    _defender_remove_all()

def _reconcile_mounts():
    """Her bilinen ISO yolunu Get-DiskImage -ImagePath ile teker teker sorgular.
    Get-DiskImage (parametresiz) bazi Windows surumlerinde bos dondugundan
    her yol ayri sorgulanir — daha guvenilir.
    _iso_mounts'u gercek Windows durumundan bastan yazar."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    # Tum bilinen ISO yollarini topla: folder_name -> iso_path
    known = {}  # folder_name -> iso_path
    for base_dir in [WIM_DIR, ISO_WIN_DIR, ISO_LIN_DIR]:
        if not os.path.exists(base_dir): continue
        for entry in os.listdir(base_dir):
            ep = os.path.join(base_dir, entry)
            if not os.path.isdir(ep): continue
            iso_path = _find_iso_path(entry)
            if iso_path: known[entry] = iso_path
    # Her yolu ayri sorgula: Get-DiskImage -ImagePath bos donmez
    corrected = {}
    for folder, iso_path in known.items():
        try:
            ps = (f"$d = Get-DiskImage -ImagePath '{iso_path}' -EA SilentlyContinue; "
                  f"if ($d -and $d.Attached) {{ ($d | Get-Volume -EA SilentlyContinue).DriveLetter }} else {{ '' }}")
            r = subprocess.run(['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps],
                capture_output=True, text=True, startupinfo=si, timeout=15)
            drv = r.stdout.strip()
            if drv and len(drv) == 1 and drv.isalpha():
                corrected[folder] = drv
        except Exception:
            pass
    with _iso_mounts_lock:
        _iso_mounts.clear()
        _iso_mounts.update(corrected)
    return corrected

def _auto_mount_existing():
    """Sunucu başlarken mevcut WebDAV ISO'larını mount eder."""
    def _do():
        time.sleep(2)
        logs = []
        failed = []
        for base_dir in [WIM_DIR, ISO_WIN_DIR, ISO_LIN_DIR]:
            if not os.path.exists(base_dir): continue
            for entry in os.listdir(base_dir):
                ep = os.path.join(base_dir, entry)
                if not os.path.isdir(ep): continue
                has_iso = (os.path.exists(os.path.join(ep, 'source.iso')) or
                           any(f.lower().endswith('.iso') for f in os.listdir(ep)))
                if has_iso:
                    logs.append(f"Auto-mounting: {entry} from {base_dir}")
                    drv = _ensure_iso_mounted(entry)
                    logs.append(f"Result for {entry}: {drv}")
                    if not drv:
                        failed.append(entry)
        # Başarısız olanlar için bir kez daha dene (büyük ISO dosyaları geç mount olabilir)
        if failed:
            time.sleep(3)
            logs.append(f"Retrying failed mounts: {failed}")
            for entry in failed:
                drv = _ensure_iso_mounted(entry)
                logs.append(f"Retry result for {entry}: {drv}")
        # Basarisiz olanlar icin retry
        if failed:
            time.sleep(3)
            logs.append(f"Retrying: {failed}")
            for entry in list(failed):
                drv = _ensure_iso_mounted(entry)
                logs.append(f"Retry {entry}: {drv}")
        # Gercek Windows durumundan eslemeyi yeniden kur
        time.sleep(1)
        corrected = _reconcile_mounts()
        logs.append(f"Reconcile: {len(corrected)} ISO verified.")
        for folder, drv in sorted(corrected.items()):
            logs.append(f"  {folder} -> {drv}:")
        try:
            with open(os.path.join(BASE_DIR, 'pxe', 'auto_mount.log'), 'w') as lf:
                lf.write('\n'.join(logs))
        except: pass
    threading.Thread(target=_do, daemon=True).start()
def _dav_xml(body):
    return Response('<?xml version="1.0" encoding="utf-8"?>' + body, status=207,
                    headers={'Content-Type':'application/xml;charset=utf-8','DAV':'1','MS-Author-Via':'DAV'})

def _dav_prop(href, name, size, is_dir):
    h  = quote(href, safe='/:@!$&\'()*+,;=')
    rt = '<D:collection/>' if is_dir else ''
    sz = '' if is_dir else f'<D:getcontentlength>{size}</D:getcontentlength>'
    return (f'<D:response><D:href>{h}</D:href><D:propstat><D:prop>'
            f'<D:displayname>{name}</D:displayname>'
            f'<D:resourcetype>{rt}</D:resourcetype>'
            f'<D:getlastmodified>Thu, 01 Jan 2026 00:00:00 GMT</D:getlastmodified>'
            f'{sz}</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>')

@app.route('/dav/<folder>', endpoint='dav_root',       methods=['OPTIONS','PROPFIND','GET','HEAD','PUT','MKCOL','DELETE','PROPPATCH','LOCK','UNLOCK'])
@app.route('/dav/<folder>/', endpoint='dav_root_sl',   methods=['OPTIONS','PROPFIND','GET','HEAD','PUT','MKCOL','DELETE','PROPPATCH','LOCK','UNLOCK'])
@app.route('/dav/<folder>/<path:inner>', endpoint='dav_inner', methods=['OPTIONS','PROPFIND','GET','HEAD','PUT','MKCOL','DELETE','PROPPATCH','LOCK','UNLOCK'])
def webdav_iso(folder, inner=''):
    try:
        return _webdav_handler(folder, inner)
    except Exception as e:
        return Response(f'Error: {e}', status=500)

def _webdav_handler(folder, inner=''):
    method = request.method.upper()
    base   = f'/dav/{folder}/'
    if method == 'OPTIONS':
        return Response('', status=200, headers={'DAV':'1','Allow':'OPTIONS,PROPFIND,GET,HEAD,PUT,MKCOL,DELETE','MS-Author-Via':'DAV'})
    if method in ('PUT', 'MKCOL', 'DELETE', 'PROPPATCH', 'LOCK', 'UNLOCK'):
        # Dummy success for R/W requests so Windows Setup doesn't crash
        return Response('', status=200)
    drv = _ensure_iso_mounted(folder)
    if not drv:
        return Response('ISO not found or could not be mounted', status=503)
    inner     = inner.strip('/').replace('/', os.sep)
    full      = os.path.join(f"{drv}:\\", inner) if inner else f"{drv}:\\"
    is_dir    = os.path.isdir(full)
    if not os.path.exists(full): return Response('Not Found', status=404)
    if method == 'PROPFIND':
        depth = request.headers.get('Depth','1')
        href  = base + (inner.replace(os.sep,'/')+('/' if is_dir else '') if inner else '')
        name  = os.path.basename(full) or folder
        size  = 0 if is_dir else os.path.getsize(full)
        props = _dav_prop(href, name, size, is_dir)
        if is_dir and depth != '0':
            try:
                for e in sorted(os.listdir(full)):
                    ep   = os.path.join(full, e)
                    eis  = os.path.isdir(ep)
                    rel  = (inner.replace(os.sep,'/')+'/' if inner else '')+e
                    props += _dav_prop(base+rel+('/' if eis else ''), e,
                                       0 if eis else os.path.getsize(ep), eis)
            except Exception: pass
        return _dav_xml(f'<D:multistatus xmlns:D="DAV:">{props}</D:multistatus>')
    if method == 'HEAD':
        return Response('', status=200, headers={'Content-Length': str(0 if is_dir else os.path.getsize(full)),
                                                  'Accept-Ranges':'bytes','DAV':'1'})
    if method == 'GET':
        if is_dir:
            try: entries = sorted(os.listdir(full))
            except: entries = []
            parts  = [p for p in inner.replace(os.sep,'/').split('/') if p] if inner else []
            crumbs = f'<a href="/dav/{folder}/">{folder}</a>'
            cp = f'/dav/{folder}/'
            for part in parts:
                cp += part+'/'
                crumbs += f' / <a href="{cp}">{part}</a>'
            rows = ''
            if parts:
                parent = '/dav/'+folder+'/'+'/'.join(parts[:-1])
                if parts[:-1]: parent += '/'
                rows += f'<tr><td colspan="2"><a href="{parent}">⬆ ..</a></td></tr>'
            for e in entries:
                ep  = os.path.join(full, e)
                eis = os.path.isdir(ep)
                rel = (inner.replace(os.sep,'/')+'/' if inner else '')+e
                href= f'/dav/{folder}/{rel}'+('/' if eis else '')
                sz  = '—' if eis else f'{os.path.getsize(ep):,} B'
                rows += (f'<tr><td>{"📁" if eis else "📄"} <a href="{href}">{e}</a></td>'
                         f'<td style="text-align:right;padding-left:40px;color:#888">{sz}</td></tr>')
            html = (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                    f'<title>{folder} — ISO Browser | iPXE Manager</title>'
                    f'<style>body{{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:30px;max-width:900px;margin:0 auto}}'
                    f'a{{color:#4ec9b0;text-decoration:none}}a:hover{{text-decoration:underline}}'
                    f'table{{border-collapse:collapse;width:100%}}'
                    f'td{{padding:4px 8px;border-bottom:1px solid #333}}'
                    f'h1{{color:#4ec9b0;font-size:1.1rem;margin:0 0 4px 0;letter-spacing:2px}}'
                    f'h2{{color:#9cdcfe;margin:20px 0 6px 0}}'
                    f'.crumbs{{margin-bottom:20px;font-size:0.9rem;color:#888}}'
                    f'.footer{{margin-top:50px;text-align:center;color:#555;font-size:0.8rem;border-top:1px solid #2a2a2a;padding-top:18px}}'
                    f'</style></head>'
                    f'<body>'
                    f'<h1>⚡ iPXE Manager</h1>'
                    f'<hr style="border:none;border-top:1px solid #2a2a2a;margin:8px 0 24px 0">'
                    f'<h2>📀 ISO Browser</h2>'
                    f'<div class="crumbs">{crumbs}</div>'
                    f'<table>{rows}</table>'
                    f'<div class="footer">'
                    f'made by <strong style="color:#4ec9b0"><a href="https://buymeacoffee.com/abdullaherturk" target="_blank" style="color:#4ec9b0; text-decoration:none;">Abdullah ERTÜRK</a></strong><br><br>'
                    f'<a href="https://github.com/abdullah-erturk">github.com/abdullah-erturk</a>'
                    f' &nbsp;|&nbsp; '
                    f'<a href="https://erturk-dev.netlify.app">erturk-dev.netlify.app</a>'
                    f'</div>'
                    f'</body></html>')
            return Response(html, status=200, headers={'Content-Type':'text/html;charset=utf-8'})
        size  = os.path.getsize(full)
        rng   = request.headers.get('Range','')
        s, e_ = 0, size-1
        status = 200
        if rng.startswith('bytes='):
            try:
                r = rng[6:].split('-')
                s  = int(r[0]) if r[0] else size-int(r[1])
                e_ = int(r[1]) if r[1] else size-1
                status = 206
            except Exception: pass
        length = e_-s+1
        def gen():
            with open(full,'rb') as fh:
                fh.seek(s); rem = length
                while rem > 0:
                    chunk = fh.read(min(65536, rem))
                    if not chunk: break
                    rem -= len(chunk); yield chunk
        hdrs = {'Content-Length':str(length),'Content-Type':'application/octet-stream',
                'Accept-Ranges':'bytes','DAV':'1'}
        if status == 206: hdrs['Content-Range'] = f'bytes {s}-{e_}/{size}'
        return Response(stream_with_context(gen()), status=status, headers=hdrs)



@app.route('/api/languages')
def list_languages():
    lang_dir = os.path.join(BASE_DIR, 'Lang')
    try:
        langs = [f[:-4] for f in os.listdir(lang_dir) if f.lower().endswith('.ini')]
        return jsonify(sorted(langs))
    except Exception:
        return jsonify([])

@app.route('/Lang/<path:filename>')
def serve_lang(filename): return send_from_directory(os.path.join(BASE_DIR, 'Lang'), filename)

@app.route('/pxe/<path:filename>')
def serve_pxe(filename): return send_from_directory(PXE_DIR, filename)

@app.route('/api/stats')
@login_required
def get_stats():
    settings = _load_app_settings()
    clients = _get_active_clients()
    return jsonify({
        'active_connections': len(clients),
        'clients': clients,
        'default_boot': settings.get('default_boot', 'HDD'),
        'countdown': settings.get('countdown', 10),
        'file_order': settings.get('file_order', [])
    })

@app.route('/api/boot_settings', methods=['POST'])
@login_required
def set_boot_settings():
    data = request.json or {}
    settings = _load_app_settings()
    if 'default_boot' in data and data['default_boot']:
        settings['default_boot'] = str(data['default_boot'])
    if 'countdown' in data:
        try:
            settings['countdown'] = max(0, int(data['countdown']))
        except (ValueError, TypeError):
            pass
    with open(os.path.join(PXE_DIR, 'app_settings.json'), 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)
    generate_ipxe_script()
    return jsonify({'success': True})

@app.route('/api/files')
@login_required
def list_files():
    files = []; metadata = _get_metadata()
    if os.path.exists(ISO_WIN_DIR):
        for f in os.listdir(ISO_WIN_DIR):
            p = os.path.join(ISO_WIN_DIR, f)
            # Yeni yapı: alt klasör + source.iso
            if os.path.isdir(p):
                iso_p = os.path.join(p, 'source.iso')
                if os.path.exists(iso_p):
                    files.append({'name': f, 'alias': metadata.get(f, f), 'type': 'ISO_WIN',
                                  'size': f'{os.path.getsize(iso_p)/(1024*1024):.1f} MB',
                                  'date': os.path.getmtime(iso_p)})
            # Eski yapı: düz .iso dosyası (geriye dönük uyumluluk)
            elif f.lower().endswith('.iso'):
                files.append({'name': f, 'alias': metadata.get(f, f), 'type': 'ISO_WIN',
                              'size': f'{os.path.getsize(p)/(1024*1024):.1f} MB',
                              'date': os.path.getmtime(p)})
            
    if os.path.exists(ISO_LIN_DIR):
        for entry in os.listdir(ISO_LIN_DIR):
            p = os.path.join(ISO_LIN_DIR, entry)
            if os.path.isdir(p):
                iso_files = [x for x in os.listdir(p) if x.lower().endswith('.iso')]
                if iso_files:
                    iso_p = os.path.join(p, iso_files[0])
                    files.append({'name': entry, 'alias': metadata.get(entry, entry), 'type': 'ISO_LINUX', 'size': f'{os.path.getsize(iso_p)/(1024*1024):.1f} MB', 'date': os.path.getmtime(p)})
            elif os.path.isfile(p) and entry.lower().endswith('.iso'):
                files.append({'name': entry, 'alias': metadata.get(entry, entry), 'type': 'ISO_LINUX', 'size': f'{os.path.getsize(p)/(1024*1024):.1f} MB', 'date': os.path.getmtime(p)})
                
    if os.path.exists(WIM_DIR):
        for entry in os.listdir(WIM_DIR):
            folder_path = os.path.join(WIM_DIR, entry)
            if not os.path.isdir(folder_path):
                continue
            mod_flag = os.path.join(folder_path, 'modified.flag')
            iso_p = os.path.join(folder_path, 'source.iso')
            wim_p = os.path.join(folder_path, 'boot.wim')
            if os.path.exists(mod_flag) and os.path.exists(iso_p):
                files.append({'name': entry, 'alias': metadata.get(entry, entry), 'type': 'WIM_MODIFIED', 'size': f'{os.path.getsize(iso_p)/(1024*1024):.1f} MB', 'date': os.path.getmtime(folder_path)})
            elif os.path.exists(wim_p):
                files.append({'name': entry, 'alias': metadata.get(entry, entry), 'type': 'WIM', 'size': f'{os.path.getsize(wim_p)/(1024*1024):.1f} MB', 'date': os.path.getmtime(folder_path)})
    # Kayıtlı sırayı uygula
    saved_order = _load_app_settings().get('file_order', [])
    if saved_order:
        order_map = {name: i for i, name in enumerate(saved_order)}
        files.sort(key=lambda f: order_map.get(f['name'], len(saved_order)))
    return jsonify(files)

@app.route('/api/settings/get')
@login_required
def get_settings(): return jsonify(_load_app_settings())

@app.route('/api/settings/set', methods=['POST'])
@login_required
def set_settings():
    data = request.json
    with open(os.path.join(PXE_DIR, 'app_settings.json'), 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    
    scan_and_extract_manual_linux()
    generate_ipxe_script(data.get('domain'))
    return jsonify({'success': True})

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files: return jsonify({'success': False})
    file = request.files['file']
    alias = request.form.get('alias', '')
    custom_name = request.form.get('custom_name', '')
    cat = request.form.get('category', 'ISO_WIN')
    
    ext = file.filename.split('.')[-1].upper()

    if ext == 'ISO':
        if cat == 'WIM_MODIFIED':
            folder_name = secure_filename(custom_name if custom_name else alias if alias else file.filename.rsplit('.', 1)[0])
            target_dir = os.path.join(WIM_DIR, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            final_name = 'source.iso'
            target_path = os.path.join(target_dir, final_name)
            key_name = folder_name
        elif cat == 'ISO_LINUX':
            folder_name = secure_filename(custom_name if custom_name else alias if alias else file.filename.rsplit('.', 1)[0])
            target_dir = os.path.join(ISO_LIN_DIR, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            final_name = folder_name + '.iso'
            target_path = os.path.join(target_dir, final_name)
            key_name = folder_name
        else: # ISO_WIN — WIM_MODIFIED gibi alt klasör yapısı
            folder_name = secure_filename(custom_name if custom_name else alias if alias else file.filename.rsplit('.', 1)[0])
            target_dir  = os.path.join(ISO_WIN_DIR, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            final_name  = 'source.iso'
            target_path = os.path.join(target_dir, final_name)
            key_name    = folder_name
    elif ext == 'WIM':
        folder_name = secure_filename(custom_name if custom_name else alias if alias else file.filename.rsplit('.', 1)[0])
        target_dir = os.path.join(WIM_DIR, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        final_name = 'boot.wim'
        target_path = os.path.join(target_dir, final_name)
        key_name = folder_name
    else:
        return jsonify({'success': False, 'error': 'Invalid file type'})

    if os.path.exists(target_path): return jsonify({'success': False, 'error': 'exists'})

    try:
        chunk_size = 4096 * 1024 
        with open(target_path, 'wb') as f:
            while True:
                chunk = file.stream.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        
        if ext == 'ISO' and cat == 'ISO_LINUX':
            threading.Thread(
                target=_extract_linux_and_regenerate,
                args=(target_path, target_dir),
                daemon=True
            ).start()

        if ext == 'ISO' and cat == 'ISO_WIN':
            threading.Thread(
                target=_extract_win_iso_and_regenerate,
                args=(target_path, target_dir),
                daemon=True
            ).start()

        if ext == 'ISO' and cat == 'WIM_MODIFIED':
            try:
                with open(os.path.join(target_dir, 'modified.flag'), 'w', encoding='utf-8') as ff:
                    ff.write('1')
            except Exception:
                pass
            threading.Thread(
                target=_extract_wim_and_regenerate,
                args=(target_path, target_dir),
                daemon=True
            ).start()

        meta = _get_metadata()
        meta[key_name] = alias if alias else key_name
        _save_metadata(meta)
        
        generate_ipxe_script()
        if ext == 'ISO':
            return jsonify({'success': True, 'extracting': True, 'folder': key_name})
        return jsonify({'success': True})
    except Exception as e:
        if os.path.exists(target_path): os.remove(target_path)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/view_log/<folder>')
@login_required
def view_log(folder):
    for base in [WIM_DIR, ISO_WIN_DIR, ISO_LIN_DIR]:
        log_path = os.path.join(base, folder, 'extract.log')
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    return jsonify({'success': True, 'log': f.read()})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': 'Log file not found'})

@app.route('/api/upload_unattend', methods=['POST'])
@login_required
def upload_unattend():
    name = request.form.get('name', '')
    file = request.files.get('file')
    if not name or not file:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    folder_path = os.path.join(ISO_WIN_DIR, name)
    if not os.path.exists(folder_path):
        return jsonify({'success': False, 'error': 'ISO folder not found'})
    try:
        dest = os.path.join(folder_path, 'unattend.xml')
        file.save(dest)
        # Aynı zamanda mount edilmiş sürücüye de kopyala
        with _iso_mounts_lock:
            drv = _iso_mounts.get(name)
        if drv:
            try:
                shutil.copy2(dest, os.path.join(f"{drv}:\\", 'unattend.xml'))
            except Exception:
                pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mount_status')
@login_required
def mount_status():
    return jsonify({folder: drv for folder, drv in _iso_mounts.items()})

@app.route('/api/wim_extract_status/<folder>')
@login_required
def wim_extract_status(folder):
    folder_path = os.path.join(WIM_DIR, folder)
    is_linux = False
    if not os.path.exists(folder_path):
        folder_path = os.path.join(ISO_WIN_DIR, folder)
    if not os.path.exists(folder_path):
        folder_path = os.path.join(ISO_LIN_DIR, folder)
        is_linux = True
    log_path = os.path.join(folder_path, 'extract.log')
    lines    = []
    log_text = ''
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                log_text = f.read()
                lines    = [l.rstrip() for l in log_text.splitlines()]
        except Exception:
            pass
    # Done sadece GÜNCEL log'dan anla — log ilk satırı "Started." veya "Başladı." içermeli
    # VE son satırda tamamlanma işareti olmalı.
    # WinPE/Win ISO: "=== All done. ===" şart (PS bittikten SONRA Python injection yapıyor).
    # Linux: "Extraction complete." yeterli (PS'in finally bloğunda, ek işlem yok).
    is_current = ('Started.' in log_text or 'Başladı.' in log_text)
    is_done    = ('=== All done. ===' in log_text or
                  (is_linux and 'Extraction complete.' in log_text) or
                  '[ERROR]' in log_text or
                  'ISO unmounted.' in log_text)
    done = is_current and is_done
    return jsonify({'done': done, 'lines': lines})

@app.route('/api/delete', methods=['POST'])
@login_required
def delete_file():
    data = request.json
    name = data.get('name') 
    
    try:
        # Silmeden ÖNCE iso yolunu ve mount kaydını al
        iso_path_for_exclusion = _find_iso_path(name)
        with _iso_mounts_lock:
            mounted_drv = _iso_mounts.get(name)

        # Unmount: hazır fonksiyonu kullan (lock'lu, tutarlı)
        _unmount_iso(name)

        for p in [os.path.join(ISO_WIN_DIR, name), os.path.join(ISO_LIN_DIR, name), os.path.join(WIM_DIR, name)]:
            if os.path.exists(p):
                time.sleep(0.5)
                if os.path.isfile(p):
                    try: os.remove(p)
                    except: subprocess.run(['cmd', '/c', 'del', '/f', '/q', p], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    try: shutil.rmtree(p)
                    except: subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', p], creationflags=subprocess.CREATE_NO_WINDOW)

        safe_id = name.replace('.', '_').replace(' ', '_')
        cmd_dir = os.path.join(PXE_DIR, 'TOOLS', 'MS', 'dynamic', safe_id)
        if os.path.exists(cmd_dir):
            try: shutil.rmtree(cmd_dir)
            except Exception: subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', cmd_dir], creationflags=subprocess.CREATE_NO_WINDOW)

        # Defender exclusion: önceden kaydedilen yollarla temizle
        if mounted_drv:
            _defender_remove_exclude(f"{mounted_drv}:\\")
        if iso_path_for_exclusion:
            _defender_remove_exclude(iso_path_for_exclusion)

        meta = _get_metadata()
        if name in meta: del meta[name]
        _save_metadata(meta)
        
        generate_ipxe_script()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reorder', methods=['POST'])
@login_required
def reorder_files():
    try:
        order = request.json.get('order', [])
        settings = _load_app_settings()
        settings['file_order'] = order
        path = os.path.join(PXE_DIR, 'app_settings.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        generate_ipxe_script()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/edit_alias', methods=['POST'])
@login_required
def edit_alias():
    data = request.json; name = data.get('name'); alias = data.get('alias')
    meta = _get_metadata(); meta[name] = alias; _save_metadata(meta); generate_ipxe_script()
    return jsonify({'success': True})

@app.route('/api/server/status')
def server_status():
    try:
        check = subprocess.check_output(
            ['tasklist', '/FI', 'IMAGENAME eq pxesrv.exe'],
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode('latin-1')
        return jsonify({'status': 'Online' if 'pxesrv.exe' in check else 'Offline'})
    except:
        return jsonify({'status': 'Offline'})

@app.route('/api/server/start', methods=['POST'])
@login_required
def start_server():
    try:
        internal_start_pxe()
        _auto_mount_existing()
        return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

@app.route('/api/server/stop', methods=['POST'])
@login_required
def stop_server():
    try:
        internal_stop_pxe()
        _unmount_all_isos()
        return jsonify({'success': True})
    except: return jsonify({'success': False})

@app.route('/api/app/shutdown', methods=['POST'])
@login_required
def shutdown():
    def _do():
        internal_stop_pxe()
        _unmount_all_isos()
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({'success': True})

if __name__ == '__main__':
    import webbrowser

    def _open_browser():
        for _ in range(20):
            try:
                with socket.create_connection(('127.0.0.1', 8080), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.5)
        webbrowser.open('http://localhost:8080')

    internal_start_pxe()
    generate_ipxe_script()   # Tüm dynamic dosyaları (WinSetup.cmd, ipxe.cfg vb.) yeniden üret
    _auto_mount_existing()
    if '--headless' not in sys.argv:
        threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host='0.0.0.0', port=8080, threaded=True, use_reloader=False)