# CleanUp-Pc - cleanup.ps1
# Cleans temporary files and caches on Windows 10, Windows 11 and Windows Server.
#
# Safe by default: with no switches only low-risk items are cleaned.
# Optional / riskier items are opt-in switches (the GUI passes them from its checkboxes).
#
#   -DryRun            Only measure what would be removed. Nothing is deleted.
#   -CleanPrefetch     Delete Prefetch (apps start slower the first time afterwards).
#   -DisableHibernate  powercfg /hibernate off (also disables Fast Startup).
#   -CompactOS         compact /compactOS:always (slow, can make HDDs slower).
#   -RestartExplorer   Restart Explorer and rebuild the icon cache.
#   -BrowserCache      Chrome / Edge / Brave / Firefox cache (close browsers first).
#   -WindowsOld        Remove Windows.old after a Windows upgrade.
#   -EventLogs         Clear all Windows event logs.
#   -RunDism           DISM component store cleanup (can take several minutes).
#   -NoPause           Do not wait for Enter at the end (used by the GUI).

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$CleanPrefetch,
    [switch]$DisableHibernate,
    [switch]$CompactOS,
    [switch]$RestartExplorer,
    [switch]$BrowserCache,
    [switch]$WindowsOld,
    [switch]$EventLogs,
    [switch]$RunDism,
    [switch]$NoPause
)

try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

# ---- Administrator check ----------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    if ($NoPause) {
        Write-Host "ERROR: Administrator rights are required."
        exit 1
    }
    # Standalone use: relaunch elevated with the same switches.
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    foreach ($k in $PSBoundParameters.Keys) {
        if ($PSBoundParameters[$k] -is [switch] -and $PSBoundParameters[$k].IsPresent) { $argList += "-$k" }
    }
    Start-Process powershell.exe -ArgumentList $argList -Verb RunAs
    exit
}

$ErrorActionPreference = 'SilentlyContinue'
$GuiMode  = $NoPause.IsPresent
$win      = $env:windir
$sysDrive = $env:SystemDrive
$script:TotalBytes = [int64]0

# ---- Helpers ----------------------------------------------------------------
function Step {
    param([int]$Pct, [string]$Text)
    if ($GuiMode) { Write-Host "##PROGRESS:$Pct|$Text" }
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Format-Size {
    param([int64]$Bytes)
    if ($Bytes -ge 1GB)     { return ("{0:N2} GB" -f ($Bytes / 1GB)) }
    elseif ($Bytes -ge 1MB) { return ("{0:N1} MB" -f ($Bytes / 1MB)) }
    else                    { return ("{0:N0} KB" -f ($Bytes / 1KB)) }
}

function Get-PathSize {
    param([string]$Path)
    $m = Get-ChildItem -Path $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
         Measure-Object -Property Length -Sum
    if ($m.Sum) { return [int64]$m.Sum }
    return [int64]0
}

# Measures a set of paths, deletes them unless -DryRun, and prints one summary line.
function Clear-Path {
    param([string]$Label, [string[]]$Path)
    $size = [int64]0
    foreach ($p in $Path) {
        $size += Get-PathSize $p
        if (-not $DryRun) {
            Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    $script:TotalBytes += $size
    $verb = if ($DryRun) { 'would free' } else { 'cleaned' }
    Write-Host ("    {0}: {1} ({2})" -f $Label, $verb, (Format-Size $size))
}

function Get-FreeBytes {
    return [int64](New-Object System.IO.DriveInfo($sysDrive)).AvailableFreeSpace
}

# ---- Start ------------------------------------------------------------------
if ($GuiMode -eq $false) { Clear-Host }
if ($DryRun) {
    Write-Host "Scanning (dry run) - nothing will be deleted..." -ForegroundColor Cyan
} else {
    Write-Host "Starting Windows Cleanup..." -ForegroundColor Cyan
}
$freeBefore = Get-FreeBytes
Write-Host ("Free space on {0} before: {1}" -f $sysDrive, (Format-Size $freeBefore))

# Temp folders
Step 5 "Temporary files"
Clear-Path "User temp"    "$env:TEMP\*"
Clear-Path "Windows temp" "$win\Temp\*"

# Prefetch (optional)
if ($CleanPrefetch) {
    Step 15 "Prefetch"
    Clear-Path "Prefetch" "$win\Prefetch\*"
}

# Windows Update cache + Delivery Optimization
Step 25 "Windows Update cache and Delivery Optimization"
$wuWasRunning   = (Get-Service wuauserv).Status -eq 'Running'
$bitsWasRunning = (Get-Service bits).Status -eq 'Running'
if (-not $DryRun) {
    Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
    Stop-Service bits -Force -ErrorAction SilentlyContinue
}
Clear-Path "Windows Update downloads" "$win\SoftwareDistribution\Download\*"
Clear-Path "Delivery Optimization" @(
    "$win\SoftwareDistribution\DeliveryOptimization\*",
    "$env:ProgramData\Microsoft\Windows\DeliveryOptimization\Cache\*"
)
if (-not $DryRun) {
    if ($wuWasRunning)   { Start-Service wuauserv -ErrorAction SilentlyContinue }
    if ($bitsWasRunning) { Start-Service bits -ErrorAction SilentlyContinue }
}

# Thumbnails, crash reports
Step 40 "Thumbnails and crash reports"
Clear-Path "Thumbnail cache" "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\thumbcache_*.db"
Clear-Path "Crash reports (WER)" "$env:ProgramData\Microsoft\Windows\WER\*"
Clear-Path "Check-disk leftovers" "$sysDrive\found.*"

# Recycle Bin
Step 50 "Recycle Bin"
$rbSize = Get-PathSize "$sysDrive\`$Recycle.Bin\*"
$script:TotalBytes += $rbSize
if ($DryRun) {
    Write-Host ("    Recycle Bin: would free ({0})" -f (Format-Size $rbSize))
} else {
    if (Get-Command Clear-RecycleBin -ErrorAction SilentlyContinue) {
        Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    }
    Write-Host ("    Recycle Bin: emptied ({0})" -f (Format-Size $rbSize))
}

# Browser caches (optional)
if ($BrowserCache) {
    Step 58 "Browser caches"
    Write-Host "    Tip: close your browsers first, open files are skipped." -ForegroundColor Yellow
    $chromium = @(
        @{ Name = 'Chrome'; Root = "$env:LOCALAPPDATA\Google\Chrome\User Data" },
        @{ Name = 'Edge';   Root = "$env:LOCALAPPDATA\Microsoft\Edge\User Data" },
        @{ Name = 'Brave';  Root = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data" }
    )
    foreach ($b in $chromium) {
        Clear-Path $b.Name @(
            "$($b.Root)\*\Cache\*",
            "$($b.Root)\*\Code Cache\*",
            "$($b.Root)\*\GPUCache\*"
        )
    }
    Clear-Path 'Firefox' "$env:LOCALAPPDATA\Mozilla\Firefox\Profiles\*\cache2\*"
}

# Windows.old (optional)
if ($WindowsOld) {
    Step 66 "Windows.old"
    $old = "$sysDrive\Windows.old"
    if (Test-Path $old) {
        $size = Get-PathSize "$old\*"
        $script:TotalBytes += $size
        if (-not $DryRun) {
            takeown /F $old /R /D Y | Out-Null
            icacls $old /grant "*S-1-5-32-544:F" /T /C /Q | Out-Null
            Remove-Item $old -Recurse -Force -ErrorAction SilentlyContinue
        }
        $verb = if ($DryRun) { 'would free' } else { 'removed' }
        Write-Host ("    Windows.old: {0} ({1})" -f $verb, (Format-Size $size))
    } else {
        Write-Host "    Windows.old not found."
    }
}

# Event logs (optional)
if ($EventLogs) {
    Step 72 "Event logs"
    if ($DryRun) {
        Write-Host "    Event logs: would be cleared."
    } else {
        wevtutil el | ForEach-Object { wevtutil cl $_ 2>$null }
        Write-Host "    Event logs cleared."
    }
}

# Hibernate (optional)
if ($DisableHibernate) {
    Step 78 "Hibernate"
    if ($DryRun) {
        Write-Host "    Hibernate: would be turned off (frees hiberfil.sys, disables Fast Startup)."
    } else {
        powercfg /hibernate off
        Write-Host "    Hibernate turned off."
    }
}

# Component store cleanup (optional)
if ($RunDism) {
    Step 82 "Component store cleanup (DISM) - this can take a while"
    if ($DryRun) {
        Write-Host "    DISM: skipped in scan mode."
    } else {
        DISM /Online /Cleanup-Image /StartComponentCleanup
    }
}

# Compact OS (optional)
if ($CompactOS) {
    Step 92 "Compact OS"
    if ([Environment]::OSVersion.Version.Major -lt 10) {
        Write-Host "    Compact OS is not supported on this Windows version, skipped." -ForegroundColor Yellow
    } elseif ($DryRun) {
        Write-Host "    Compact OS: would be enabled."
    } else {
        compact.exe /compactOS:always
    }
}

# Explorer restart + icon cache (optional)
if ($RestartExplorer) {
    Step 96 "Explorer and icon cache"
    if (-not $DryRun) {
        Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Clear-Path "Icon cache" @(
        "$env:LOCALAPPDATA\IconCache.db",
        "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\iconcache_*.db"
    )
    if (-not $DryRun) {
        # Start Explorer with a normal (non-elevated) token so it does not run as admin.
        Start-Process -FilePath "$win\System32\runas.exe" `
            -ArgumentList '/trustlevel:0x20000', 'explorer.exe' -WindowStyle Hidden
        Start-Sleep -Seconds 3
        if (-not (Get-Process -Name explorer -ErrorAction SilentlyContinue)) {
            Start-Process explorer.exe
        }
    }
}

# DNS cache
if (-not $DryRun) {
    Step 98 "DNS cache"
    if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {
        Clear-DnsClientCache
    } else {
        ipconfig /flushdns | Out-Null
    }
    Write-Host "    DNS cache cleared."
}

# ---- Summary ----------------------------------------------------------------
if ($GuiMode) { Write-Host "##PROGRESS:100|Done" }
Write-Host ""
if ($DryRun) {
    Write-Host ("Scan complete: about {0} can be freed." -f (Format-Size $script:TotalBytes)) -ForegroundColor Green
    Write-Host "Scan Finished Successfully!" -ForegroundColor Green
} else {
    $freed = (Get-FreeBytes) - $freeBefore
    if ($freed -lt 0) { $freed = 0 }
    Write-Host ("Free space on {0} after: {1}" -f $sysDrive, (Format-Size (Get-FreeBytes)))
    Write-Host ("Freed: {0}" -f (Format-Size $freed)) -ForegroundColor Green
    Write-Host "Cleanup Finished Successfully!" -ForegroundColor Green
}

if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
exit 0
