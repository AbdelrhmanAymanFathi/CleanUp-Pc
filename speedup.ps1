# SpeedUp-Windows.ps1
# Performance tuning for Windows 10, Windows 11, and Windows Server.
# Automatically runs as Administrator.
# Tip: create a restore point before running if you want an easy rollback.

# ----------------------------- Options --------------------------------------
# Change these before running if needed.
$KeepSearchIndexing  = $true    # $false disables Windows Search (may break Start menu search)
$KeepSysMain         = $true    # $false disables SysMain / Superfetch
$DisableXboxServices = $false   # $true disables Xbox services (breaks the Xbox app and Game Pass)
$DisableTelemetry    = $true    # $false keeps telemetry services and scheduled tasks
# ----------------------------------------------------------------------------

# Auto Run as Administrator
if (-not ([Security.Principal.WindowsPrincipal] `
[Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(`
[Security.Principal.WindowsBuiltInRole] "Administrator"))
{
    Start-Process powershell.exe `
    -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
    -Verb RunAs
    exit
}

$ErrorActionPreference = "SilentlyContinue"

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Set-RegValue {
    param(
        [string]$Path,
        [string]$Name,
        $Value,
        [string]$Type = "DWord"
    )

    if (-not (Test-Path $Path)) {
        New-Item -Path $Path -Force | Out-Null
    }
    Set-ItemProperty -Path $Path -Name $Name -Value $Value -Type $Type -Force -ErrorAction SilentlyContinue
}

function Disable-ServiceSafe {
    param([string]$Name)

    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $service) { return }

    if ($service.Status -ne "Stopped") {
        Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
    }
    Set-Service -Name $Name -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Host "    Disabled service: $Name"
}

function Disable-TaskSafe {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue)) { return }

    $task = Get-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $task) { return }

    Disable-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue | Out-Null
    Write-Host "    Disabled task: $Name"
}

Clear-Host
Write-Host "Starting Windows Speed Up..." -ForegroundColor Cyan

# Detect Windows edition
$os = Get-CimInstance Win32_OperatingSystem
$isServer = $os.ProductType -ne 1

Write-Host "Detected: $($os.Caption)" -ForegroundColor Yellow
if ($isServer) {
    Write-Host "Server mode: client-only tweaks will be skipped." -ForegroundColor Yellow
} else {
    Write-Host "Desktop mode: client performance tweaks will be applied." -ForegroundColor Yellow
}

if (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue) {
    Write-Host "Laptop detected: the High Performance plan uses more battery." -ForegroundColor Yellow
}

# Power Plan
Write-Step "Setting power plan to High Performance..."

powercfg /setactive SCHEME_MIN 2>$null
if ($LASTEXITCODE -ne 0) {
    powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "    Power plan updated."
} else {
    Write-Host "    Could not change the power plan. Set it manually." -ForegroundColor Yellow
}

# Client-only tweaks
if (-not $isServer) {
    Write-Step "Configuring visual performance..."

    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" "VisualFXSetting" 2
    Set-RegValue "HKCU:\Control Panel\Desktop" "MenuShowDelay" "0" "String"
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "EnableTransparency" 0

    Write-Host "    Visual effects set to best performance."

    Write-Step "Disabling background apps and Game DVR..."

    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" "GlobalUserDisabled" 1
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" "BackgroundAppGlobalToggle" 0
    Set-RegValue "HKCU:\System\GameConfigStore" "GameDVR_Enabled" 0
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR" "AppCaptureEnabled" 0

    Write-Host "    Background apps and Game DVR disabled."

    Write-Step "Reducing Windows tips and suggestions..."

    $contentDelivery = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    Set-RegValue $contentDelivery "SoftLandingEnabled" 0
    Set-RegValue $contentDelivery "SystemPaneSuggestionsEnabled" 0
    Set-RegValue $contentDelivery "SubscribedContent-338388Enabled" 0
    Set-RegValue $contentDelivery "SubscribedContent-338389Enabled" 0

    Write-Host "    Tips and suggestions turned off."
}

# Services
Write-Step "Tuning services..."

if ($DisableTelemetry) {
    Disable-ServiceSafe "DiagTrack"
    Disable-ServiceSafe "dmwappushservice"
}

if (-not $isServer) {
    Disable-ServiceSafe "RetailDemo"
    Disable-ServiceSafe "Fax"
}

if (-not $KeepSysMain) {
    Disable-ServiceSafe "SysMain"
}

if (-not $KeepSearchIndexing) {
    Disable-ServiceSafe "WSearch"
}

if ($DisableXboxServices -and -not $isServer) {
    Disable-ServiceSafe "XblAuthManager"
    Disable-ServiceSafe "XblGameSave"
    Disable-ServiceSafe "XboxGipSvc"
    Disable-ServiceSafe "XboxNetApiSvc"
}

Write-Host "    Service tuning complete."

# Telemetry Scheduled Tasks
if ($DisableTelemetry) {
    Write-Step "Disabling telemetry scheduled tasks..."

    $tasks = @(
        @{ Path = "\Microsoft\Windows\Application Experience\"; Name = "ProgramDataUpdater" },
        @{ Path = "\Microsoft\Windows\Application Experience\"; Name = "Microsoft Compatibility Appraiser" },
        @{ Path = "\Microsoft\Windows\Customer Experience Improvement Program\"; Name = "Consolidator" },
        @{ Path = "\Microsoft\Windows\Customer Experience Improvement Program\"; Name = "UsbCeip" },
        @{ Path = "\Microsoft\Windows\Feedback\Siuf\"; Name = "DmClient" },
        @{ Path = "\Microsoft\Windows\Feedback\Siuf\"; Name = "DmClientOnScenarioDownload" },
        @{ Path = "\Microsoft\Windows\Autochk\"; Name = "Proxy" }
    )

    foreach ($task in $tasks) {
        Disable-TaskSafe -Path $task.Path -Name $task.Name
    }
}

# Storage
Write-Step "Optimizing storage settings..."

fsutil behavior set DisableDeleteNotify 0 | Out-Null
Write-Host "    TRIM enabled for SSDs."

# Network
Write-Step "Flushing DNS cache..."

Clear-DnsClientCache
Write-Host "    DNS cache cleared."

# Startup Programs
Write-Step "Startup programs (disable unused ones in Task Manager)..."

Get-CimInstance Win32_StartupCommand |
    Select-Object Name, Location |
    Format-Table -AutoSize

Write-Host ""
Write-Host "Speed Up Finished Successfully!" -ForegroundColor Green
Write-Host "Restart Windows to apply all changes." -ForegroundColor Yellow
Write-Host ""
Pause
