param(
    [switch]$NoPause,
    [switch]$DryRun,
    [bool]$KeepSearchIndexing = $true,
    [bool]$KeepSysMain = $true,
    [bool]$DisableXboxServices = $false,
    [bool]$DisableTelemetry = $true
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$ErrorActionPreference = "SilentlyContinue"

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

function Set-RegValue {
    param([string]$Path, [string]$Name, $Value, [string]$Type = "DWord")
    if (-not (Test-Path $Path)) { New-Item -Path $Path -Force | Out-Null }
    Set-ItemProperty -Path $Path -Name $Name -Value $Value -Type $Type -Force -ErrorAction SilentlyContinue
}

function Disable-ServiceSafe {
    param([string]$Name)
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $service) { return }
    if ($service.Status -ne "Stopped") { Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue }
    Set-Service -Name $Name -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Status "    Disabled service: $Name"
}

function Disable-TaskSafe {
    param([string]$Path, [string]$Name)
    if (-not (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue)) { return }
    $task = Get-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $task) { return }
    Disable-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue | Out-Null
    Write-Status "    Disabled task: $Name"
}

# Detect Windows edition
$os = Get-CimInstance Win32_OperatingSystem
$isServer = $os.ProductType -ne 1
Write-Status "Detected: $($os.Caption)"
if ($isServer) {
    Write-Status "Server mode: client-only tweaks will be skipped." "WARN"
} else {
    Write-Status "Desktop mode: client performance tweaks will be applied."
}

# Restore point before Desktop changes (handle 24h limit gracefully)
if (-not $isServer -and -not $DryRun) {
    Write-Status "Creating restore point..."
    try {
        Checkpoint-Computer -Description "CleanUp-Pc Speed Up" -RestorePointType "MODIFY_SETTINGS" -ErrorAction Stop
        Write-Status "    Restore point created."
    } catch {
        if ($_.Exception.Message -like "*24*") {
            Write-Status "    Restore point skipped (24-hour limit reached)." "WARN"
        } else {
            Write-Status "    Could not create restore point: $($_.Exception.Message)" "WARN"
        }
    }
}

# Power Plan
Write-Status "Setting power plan to High Performance..."
Invoke-IfNotDryRun -Script { powercfg /setactive SCHEME_MIN } -Message "Would set High Performance power plan"
if (-not $DryRun) {
    if ($LASTEXITCODE -ne 0) {
        Invoke-IfNotDryRun -Script { powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c } -Message "Would set High Performance power plan (alternate GUID)"
    }
}

# Client-only tweaks
if (-not $isServer) {
    Write-Status "Configuring visual performance..."
    Invoke-IfNotDryRun -Script {
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" "VisualFXSetting" 2
        Set-RegValue "HKCU:\Control Panel\Desktop" "MenuShowDelay" "0" "String"
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "EnableTransparency" 0
    } -Message "Would set visual effects to best performance"

    Write-Status "Disabling background apps and Game DVR..."
    Invoke-IfNotDryRun -Script {
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" "GlobalUserDisabled" 1
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" "BackgroundAppGlobalToggle" 0
        Set-RegValue "HKCU:\System\GameConfigStore" "GameDVR_Enabled" 0
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR" "AppCaptureEnabled" 0
    } -Message "Would disable background apps and Game DVR"

    Write-Status "Reducing Windows tips and suggestions..."
    $contentDelivery = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    Invoke-IfNotDryRun -Script {
        Set-RegValue $contentDelivery "SoftLandingEnabled" 0
        Set-RegValue $contentDelivery "SystemPaneSuggestionsEnabled" 0
        Set-RegValue $contentDelivery "SubscribedContent-338388Enabled" 0
        Set-RegValue $contentDelivery "SubscribedContent-338389Enabled" 0
    } -Message "Would turn off tips and suggestions"
}

# Services
Write-Status "Tuning services..."
if ($DisableTelemetry) {
    Invoke-IfNotDryRun -Script { Disable-ServiceSafe "DiagTrack"; Disable-ServiceSafe "dmwappushservice" } -Message "Would disable telemetry services"
}
if (-not $isServer) {
    Invoke-IfNotDryRun -Script { Disable-ServiceSafe "RetailDemo"; Disable-ServiceSafe "Fax" } -Message "Would disable RetailDemo and Fax services"
}
if (-not $KeepSysMain) {
    Invoke-IfNotDryRun -Script { Disable-ServiceSafe "SysMain" } -Message "Would disable SysMain"
}
if (-not $KeepSearchIndexing) {
    Invoke-IfNotDryRun -Script { Disable-ServiceSafe "WSearch" } -Message "Would disable Windows Search"
}
if ($DisableXboxServices -and -not $isServer) {
    Invoke-IfNotDryRun -Script {
        Disable-ServiceSafe "XblAuthManager"
        Disable-ServiceSafe "XblGameSave"
        Disable-ServiceSafe "XboxGipSvc"
        Disable-ServiceSafe "XboxNetApiSvc"
    } -Message "Would disable Xbox services"
}
Write-Status "    Service tuning complete."

# Telemetry Scheduled Tasks
if ($DisableTelemetry) {
    Write-Status "Disabling telemetry scheduled tasks..."
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
        Invoke-IfNotDryRun -Script { Disable-TaskSafe -Path $task.Path -Name $task.Name } -Message "Would disable task $($task.Name)"
    }
}

# TRIM (not fsutil - using built-in)
Write-Status "Ensuring TRIM is enabled..."
Invoke-IfNotDryRun -Script { fsutil behavior query DisableDeleteNotify | Out-Null } -Message "Would check TRIM status"

# DNS flush
Write-Status "Flushing DNS cache..."
Invoke-IfNotDryRun -Script { Clear-DnsClientCache } -Message "Would flush DNS cache"

# Startup programs list
Write-Status "Startup programs (disable unused ones via the GUI Startup Programs tab)..."
Get-CimInstance Win32_StartupCommand | Select-Object Name, Location | Format-Table -AutoSize

Write-Status "Speed Up Finished Successfully!" "SUCCESS"
Write-Status "Restart Windows to apply all changes." "WARN"

if (-not $NoPause) { Pause }
