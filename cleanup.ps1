param(
    [switch]$NoPause,
    [switch]$DryRun,
    [bool]$CleanTemp = $true,
    [bool]$CleanWindowsTemp = $true,
    [bool]$CleanPrefetch = $false,
    [bool]$CleanUpdateCache = $true,
    [bool]$CleanDeliveryOpt = $true,
    [bool]$CleanDns = $true,
    [bool]$CleanIconCache = $true,
    [bool]$CleanThumbnailCache = $true,
    [bool]$CleanCrashLogs = $true,
    [bool]$CleanRecycleBin = $true,
    [bool]$DisableHibernate = $false,
    [bool]$CompactOS = $false,
    [bool]$CleanChromeCache = $false,
    [bool]$CleanEdgeCache = $false,
    [bool]$CleanFirefoxCache = $false,
    [bool]$CleanWindowsOld = $false,
    [bool]$CleanChkFiles = $false,
    [bool]$CleanEventLogs = $false
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"
$windir = $env:windir
$local = $env:LOCALAPPDATA

# Self-elevation only for standalone use (when -NoPause is NOT set)
if (-not $NoPause) {
    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
        Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
        exit
    }
}

function Write-Status {
    param([string]$Message, [string]$Level = "INFO")
    Write-Host "[$Level] $Message"
}

function Invoke-IfNotDryRun {
    param([scriptblock]$Script, [string]$Message)
    if ($DryRun) {
        Write-Status $Message "DRYRUN"
    } else {
        & $Script
    }
}

# Measure free space before
$diskBefore = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$startFreeGB = [math]::Round($diskBefore.FreeSpace / 1GB, 2)
Write-Status "Free space before: $startFreeGB GB"

# --- User Temp ---
if ($CleanTemp) {
    Write-Status "Cleaning User Temp..."
    Invoke-IfNotDryRun -Script { Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean User Temp ($env:TEMP)"
}

# --- Windows Temp ---
if ($CleanWindowsTemp) {
    Write-Status "Cleaning Windows Temp..."
    Invoke-IfNotDryRun -Script { Remove-Item "$windir\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Windows Temp ($windir\Temp)"
}

# --- Prefetch (optional, OFF by default) ---
if ($CleanPrefetch) {
    Write-Status "Cleaning Prefetch..."
    Invoke-IfNotDryRun -Script { Remove-Item "$windir\Prefetch\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Prefetch ($windir\Prefetch)"
}

# --- Windows Update Cache ---
if ($CleanUpdateCache) {
    Write-Status "Cleaning Windows Update Cache..."
    Invoke-IfNotDryRun -Script {
        Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
        Remove-Item "$windir\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
        Start-Service wuauserv -ErrorAction SilentlyContinue
    } -Message "Would clean Windows Update cache"
}

# --- Delivery Optimization ---
if ($CleanDeliveryOpt) {
    Write-Status "Cleaning Delivery Optimization..."
    Invoke-IfNotDryRun -Script { Remove-Item "$windir\SoftwareDistribution\DeliveryOptimization\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Delivery Optimization"
}

# --- DNS Cache ---
if ($CleanDns) {
    Write-Status "Clearing DNS cache..."
    Invoke-IfNotDryRun -Script { Clear-DnsClientCache -ErrorAction SilentlyContinue } -Message "Would clear DNS cache"
}

# --- Icon Cache (fixed path) ---
if ($CleanIconCache) {
    Write-Status "Cleaning Icon Cache..."
    Invoke-IfNotDryRun -Script {
        Remove-Item "$local\IconCache.db" -Force -ErrorAction SilentlyContinue
        Remove-Item "$local\Microsoft\Windows\Explorer\iconcache_*.db" -Force -ErrorAction SilentlyContinue
    } -Message "Would clean Icon Cache"
}

# --- Thumbnail Cache ---
if ($CleanThumbnailCache) {
    Write-Status "Cleaning Thumbnail Cache..."
    Invoke-IfNotDryRun -Script { Remove-Item "$local\Microsoft\Windows\Explorer\thumbcache_*" -Force -ErrorAction SilentlyContinue } -Message "Would clean Thumbnail Cache"
}

# --- Crash Logs ---
if ($CleanCrashLogs) {
    Write-Status "Cleaning Crash Logs..."
    Invoke-IfNotDryRun -Script { Remove-Item "$env:ProgramData\Microsoft\Windows\WER\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Crash Logs"
}

# --- Recycle Bin ---
if ($CleanRecycleBin) {
    Write-Status "Emptying Recycle Bin..."
    Invoke-IfNotDryRun -Script { Clear-RecycleBin -Force -ErrorAction SilentlyContinue } -Message "Would empty Recycle Bin"
}

# --- Disable Hibernation (optional, OFF by default) ---
if ($DisableHibernate) {
    Write-Status "Disabling Hibernate..."
    Invoke-IfNotDryRun -Script { powercfg /hibernate off } -Message "Would disable hibernation"
}

# --- Compact OS (optional, OFF by default) ---
if ($CompactOS) {
    Write-Status "Running DISM Cleanup..."
    Invoke-IfNotDryRun -Script { DISM /Online /Cleanup-Image /StartComponentCleanup } -Message "Would run DISM cleanup"
    Write-Status "Compacting OS..."
    Invoke-IfNotDryRun -Script { compact.exe /compactOS:always } -Message "Would compact OS"
}

# --- Optional: Browser caches ---
if ($CleanChromeCache) {
    Write-Status "Cleaning Chrome cache..."
    Invoke-IfNotDryRun -Script { Remove-Item "$local\Google\Chrome\User Data\*\Cache\*" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item "$local\Google\Chrome\User Data\*\Code Cache\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Chrome cache"
}
if ($CleanEdgeCache) {
    Write-Status "Cleaning Edge cache..."
    Invoke-IfNotDryRun -Script { Remove-Item "$local\Microsoft\Edge\User Data\*\Cache\*" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item "$local\Microsoft\Edge\User Data\*\Code Cache\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Edge cache"
}
if ($CleanFirefoxCache) {
    Write-Status "Cleaning Firefox cache..."
    Invoke-IfNotDryRun -Script { Remove-Item "$local\Mozilla\Firefox\Profiles\*\cache2\*" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean Firefox cache"
}

# --- Optional: Windows.old ---
if ($CleanWindowsOld) {
    Write-Status "Cleaning Windows.old..."
    Invoke-IfNotDryRun -Script { Remove-Item "$env:systemdrive\Windows.old" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would remove Windows.old"
}

# --- Optional: .chk files ---
if ($CleanChkFiles) {
    Write-Status "Cleaning .chk files..."
    Invoke-IfNotDryRun -Script { Remove-Item "$env:systemdrive\found.000\*.chk" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item "$env:systemdrive\found.001\*.chk" -Recurse -Force -ErrorAction SilentlyContinue } -Message "Would clean .chk files"
}

# --- Optional: Old Event Logs ---
if ($CleanEventLogs) {
    Write-Status "Cleaning old Event Logs..."
    Invoke-IfNotDryRun -Script {
        Get-WinEvent -ListLog * -ErrorAction SilentlyContinue | ForEach-Object {
            try { Clear-EventLog -LogName $_.LogName -ErrorAction Stop } catch {}
        }
    } -Message "Would clear old Event Logs"
}

# Measure free space after
$diskAfter = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$endFreeGB = [math]::Round($diskAfter.FreeSpace / 1GB, 2)
$freedGB = [math]::Round($endFreeGB - $startFreeGB, 2)
Write-Status "Free space after: $endFreeGB GB"
Write-Status "Freed $freedGB GB" "SUCCESS"

if (-not $NoPause) { Pause }
