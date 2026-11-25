# CleanUp-Pc - speedup.ps1
# Performance tuning for Windows 10, Windows 11 and Windows Server.
#
# Every change is recorded in %ProgramData%\CleanUp-Pc\speedup-backup.json so that
# restore-defaults.ps1 (or the "Undo Speed Up" button) can put things back exactly.
#
#   -KeepTelemetry   Do not disable telemetry services / scheduled tasks.
#   -DisableSysMain  Disable SysMain (Superfetch).
#   -DisableSearch   Disable Windows Search (Start menu search may stop working).
#   -DisableXbox     Disable Xbox services (breaks the Xbox app and Game Pass).
#   -NoRestorePoint  Do not create a system restore point first (Desktop only).
#   -NoPause         Do not wait for Enter at the end (used by the GUI).

[CmdletBinding()]
param(
    [switch]$KeepTelemetry,
    [switch]$DisableSysMain,
    [switch]$DisableSearch,
    [switch]$DisableXbox,
    [switch]$NoRestorePoint,
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
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    foreach ($k in $PSBoundParameters.Keys) {
        if ($PSBoundParameters[$k] -is [switch] -and $PSBoundParameters[$k].IsPresent) { $argList += "-$k" }
    }
    Start-Process powershell.exe -ArgumentList $argList -Verb RunAs
    exit
}

$ErrorActionPreference = 'SilentlyContinue'
$GuiMode = $NoPause.IsPresent

# ---- Backup state -----------------------------------------------------------
$BackupDir  = Join-Path $env:ProgramData 'CleanUp-Pc'
$BackupFile = Join-Path $BackupDir 'speedup-backup.json'
$Backup = [ordered]@{
    Created     = (Get-Date).ToString('s')
    PowerScheme = $null
    Services    = @()
    Tasks       = @()
    Registry    = @()
}
# Keep the ORIGINAL state if Speed Up was already run before.
if (Test-Path $BackupFile) {
    try {
        $old = Get-Content -Path $BackupFile -Raw -ErrorAction Stop | ConvertFrom-Json
        $Backup.Created     = $old.Created
        $Backup.PowerScheme = $old.PowerScheme
        $Backup.Services    = @($old.Services | Where-Object { $_ })
        $Backup.Tasks       = @($old.Tasks    | Where-Object { $_ })
        $Backup.Registry    = @($old.Registry | Where-Object { $_ })
    } catch {}
}

function Save-Backup {
    if (-not (Test-Path $BackupDir)) { New-Item -Path $BackupDir -ItemType Directory -Force | Out-Null }
    $Backup | ConvertTo-Json -Depth 6 | Set-Content -Path $BackupFile -Encoding UTF8
}

# ---- Helpers ----------------------------------------------------------------
function Step {
    param([int]$Pct, [string]$Text)
    if ($GuiMode) { Write-Host "##PROGRESS:$Pct|$Text" }
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Save-RegBackup {
    param([string]$Path, [string]$Name)
    if ($Backup.Registry | Where-Object { $_.Path -eq $Path -and $_.Name -eq $Name }) { return }
    $existed = $false; $value = $null; $kind = $null
    try {
        $item = Get-Item -Path $Path -ErrorAction Stop
        if ($item.GetValueNames() -contains $Name) {
            $existed = $true
            $value   = $item.GetValue($Name, $null, 'DoNotExpandEnvironmentNames')
            $kind    = $item.GetValueKind($Name).ToString()
        }
    } catch {}
    $Backup.Registry += [pscustomobject]@{ Path = $Path; Name = $Name; Existed = $existed; Value = $value; Kind = $kind }
}

function Set-RegValue {
    param([string]$Path, [string]$Name, $Value, [string]$Type = "DWord")
    Save-RegBackup -Path $Path -Name $Name
    if (-not (Test-Path $Path)) { New-Item -Path $Path -Force | Out-Null }
    Set-ItemProperty -Path $Path -Name $Name -Value $Value -Type $Type -Force -ErrorAction SilentlyContinue
}

function Disable-ServiceSafe {
    param([string]$Name)
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $service) { return }

    $svcReg  = "HKLM:\SYSTEM\CurrentControlSet\Services\$Name"
    $start   = (Get-ItemProperty -Path $svcReg -Name Start -ErrorAction SilentlyContinue).Start
    $delayed = (Get-ItemProperty -Path $svcReg -Name DelayedAutostart -ErrorAction SilentlyContinue).DelayedAutostart
    if ($start -eq 4) { return }   # already disabled

    if (-not ($Backup.Services | Where-Object { $_.Name -eq $Name })) {
        $Backup.Services += [pscustomobject]@{ Name = $Name; Start = $start; Delayed = [int]$delayed }
    }
    if ($service.Status -ne "Stopped") { Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue }
    Set-Service -Name $Name -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Host "    Disabled service: $Name"
}

function Disable-TaskSafe {
    param([string]$Path, [string]$Name)
    if (-not (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue)) { return }
    $task = Get-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $task -or $task.State -eq 'Disabled') { return }

    if (-not ($Backup.Tasks | Where-Object { $_.Path -eq $Path -and $_.Name -eq $Name })) {
        $Backup.Tasks += [pscustomobject]@{ Path = $Path; Name = $Name }
    }
    Disable-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue | Out-Null
    Write-Host "    Disabled task: $Name"
}

# ---- Start ------------------------------------------------------------------
if (-not $GuiMode) { Clear-Host }
Write-Host "Starting Windows Speed Up..." -ForegroundColor Cyan

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

# Restore point (Desktop only)
if (-not $isServer -and -not $NoRestorePoint) {
    Step 5 "Creating a system restore point"
    try {
        Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction Stop
        Checkpoint-Computer -Description "CleanUp-Pc before Speed Up" -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
        Write-Host "    Restore point created."
    } catch {
        Write-Host "    Could not create a restore point (skipped): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Power plan
Step 15 "Setting power plan to High Performance"
$current = (powercfg /getactivescheme) | Out-String
if (-not $Backup.PowerScheme -and $current -match '([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})') {
    if ($Matches[1] -ne '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c') { $Backup.PowerScheme = $Matches[1] }
}
powercfg /setactive SCHEME_MIN 2>$null
if ($LASTEXITCODE -ne 0) { powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null }
if ($LASTEXITCODE -eq 0) {
    Write-Host "    Power plan updated."
} else {
    Write-Host "    Could not change the power plan. Set it manually." -ForegroundColor Yellow
}

# Client-only tweaks
if (-not $isServer) {
    Step 30 "Configuring visual performance"
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" "VisualFXSetting" 2
    Set-RegValue "HKCU:\Control Panel\Desktop" "MenuShowDelay" "0" "String"
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "EnableTransparency" 0
    Write-Host "    Visual effects set to best performance (sign out to fully apply)."

    Step 42 "Disabling background apps and Game DVR"
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" "GlobalUserDisabled" 1
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" "BackgroundAppGlobalToggle" 0
    Set-RegValue "HKCU:\System\GameConfigStore" "GameDVR_Enabled" 0
    Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR" "AppCaptureEnabled" 0
    Write-Host "    Background apps and Game DVR disabled."

    Step 52 "Reducing Windows tips and suggestions"
    $cd = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    Set-RegValue $cd "SoftLandingEnabled" 0
    Set-RegValue $cd "SystemPaneSuggestionsEnabled" 0
    Set-RegValue $cd "SubscribedContent-338388Enabled" 0
    Set-RegValue $cd "SubscribedContent-338389Enabled" 0
    Write-Host "    Tips and suggestions turned off."
}

# Services
Step 65 "Tuning services"
if (-not $KeepTelemetry) {
    Disable-ServiceSafe "DiagTrack"
    Disable-ServiceSafe "dmwappushservice"
}
if (-not $isServer) {
    Disable-ServiceSafe "RetailDemo"
    Disable-ServiceSafe "Fax"
}
if ($DisableSysMain)  { Disable-ServiceSafe "SysMain" }
if ($DisableSearch)   { Disable-ServiceSafe "WSearch" }
if ($DisableXbox -and -not $isServer) {
    Disable-ServiceSafe "XblAuthManager"
    Disable-ServiceSafe "XblGameSave"
    Disable-ServiceSafe "XboxGipSvc"
    Disable-ServiceSafe "XboxNetApiSvc"
}
Write-Host "    Service tuning complete."

# Telemetry scheduled tasks
if (-not $KeepTelemetry) {
    Step 82 "Disabling telemetry scheduled tasks"
    $tasks = @(
        @{ Path = "\Microsoft\Windows\Application Experience\"; Name = "ProgramDataUpdater" },
        @{ Path = "\Microsoft\Windows\Application Experience\"; Name = "Microsoft Compatibility Appraiser" },
        @{ Path = "\Microsoft\Windows\Customer Experience Improvement Program\"; Name = "Consolidator" },
        @{ Path = "\Microsoft\Windows\Customer Experience Improvement Program\"; Name = "UsbCeip" },
        @{ Path = "\Microsoft\Windows\Feedback\Siuf\"; Name = "DmClient" },
        @{ Path = "\Microsoft\Windows\Feedback\Siuf\"; Name = "DmClientOnScenarioDownload" },
        @{ Path = "\Microsoft\Windows\Autochk\"; Name = "Proxy" }
    )
    foreach ($t in $tasks) { Disable-TaskSafe -Path $t.Path -Name $t.Name }
}

# DNS
Step 92 "Flushing DNS cache"
if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) { Clear-DnsClientCache } else { ipconfig /flushdns | Out-Null }
Write-Host "    DNS cache cleared."

Save-Backup
Write-Host "    Undo information saved to: $BackupFile"

if ($GuiMode) { Write-Host "##PROGRESS:100|Done" }
Write-Host ""
Write-Host "Speed Up Finished Successfully!" -ForegroundColor Green
Write-Host "Restart Windows to apply all changes. Use 'Undo Speed Up' to revert." -ForegroundColor Yellow
Write-Host "Manage startup programs from the 'Startup Manager' button." -ForegroundColor Yellow

if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
exit 0
