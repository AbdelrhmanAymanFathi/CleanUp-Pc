param(
    [switch]$NoPause,
    [switch]$DryRun
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

function Enable-ServiceSafe {
    param([string]$Name, [string]$Startup = "Automatic")
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $service) { return }
    Start-Service -Name $Name -ErrorAction SilentlyContinue
    Set-Service -Name $Name -StartupType $Startup -ErrorAction SilentlyContinue
    Write-Status "    Restored service: $Name ($Startup)"
}

function Enable-TaskSafe {
    param([string]$Path, [string]$Name)
    if (-not (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue)) { return }
    $task = Get-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $task) { return }
    Enable-ScheduledTask -TaskPath $Path -TaskName $Name -ErrorAction SilentlyContinue | Out-Null
    Write-Status "    Restored task: $Name"
}

$os = Get-CimInstance Win32_OperatingSystem
$isServer = $os.ProductType -ne 1

Write-Status "Restoring Windows defaults..."

# Re-enable services
Write-Status "Re-enabling services..."
Invoke-IfNotDryRun -Script { Enable-ServiceSafe "DiagTrack" "Automatic" } -Message "Would restore DiagTrack"
Invoke-IfNotDryRun -Script { Enable-ServiceSafe "dmwappushservice" "Manual" } -Message "Would restore dmwappushservice"
if (-not $isServer) {
    Invoke-IfNotDryRun -Script { Enable-ServiceSafe "RetailDemo" "Manual"; Enable-ServiceSafe "Fax" "Manual" } -Message "Would restore RetailDemo and Fax"
}
Invoke-IfNotDryRun -Script { Enable-ServiceSafe "SysMain" "Automatic" } -Message "Would restore SysMain"
Invoke-IfNotDryRun -Script { Enable-ServiceSafe "WSearch" "Automatic" } -Message "Would restore Windows Search"
if (-not $isServer) {
    Invoke-IfNotDryRun -Script {
        Enable-ServiceSafe "XblAuthManager" "Manual"
        Enable-ServiceSafe "XblGameSave" "Manual"
        Enable-ServiceSafe "XboxGipSvc" "Manual"
        Enable-ServiceSafe "XboxNetApiSvc" "Manual"
    } -Message "Would restore Xbox services"
}

# Re-enable scheduled tasks
Write-Status "Re-enabling telemetry scheduled tasks..."
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
    Invoke-IfNotDryRun -Script { Enable-TaskSafe -Path $task.Path -Name $task.Name } -Message "Would restore task $($task.Name)"
}

# Revert registry values
Write-Status "Reverting registry tweaks..."
if (-not $isServer) {
    Invoke-IfNotDryRun -Script {
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" "VisualFXSetting" 0
        Set-RegValue "HKCU:\Control Panel\Desktop" "MenuShowDelay" "400" "String"
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "EnableTransparency" 1
    } -Message "Would revert visual effects"
    Invoke-IfNotDryRun -Script {
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" "GlobalUserDisabled" 0
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" "BackgroundAppGlobalToggle" 1
        Set-RegValue "HKCU:\System\GameConfigStore" "GameDVR_Enabled" 1
        Set-RegValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR" "AppCaptureEnabled" 1
    } -Message "Would revert background apps and Game DVR"
    $contentDelivery = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
    Invoke-IfNotDryRun -Script {
        Set-RegValue $contentDelivery "SoftLandingEnabled" 1
        Set-RegValue $contentDelivery "SystemPaneSuggestionsEnabled" 1
        Set-RegValue $contentDelivery "SubscribedContent-338388Enabled" 1
        Set-RegValue $contentDelivery "SubscribedContent-338389Enabled" 1
    } -Message "Would re-enable tips and suggestions"
}

# Restore power plan to Balanced
Write-Status "Restoring power plan to Balanced..."
Invoke-IfNotDryRun -Script { powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e } -Message "Would set Balanced power plan"
if (-not $DryRun) {
    if ($LASTEXITCODE -ne 0) {
        Invoke-IfNotDryRun -Script { powercfg /setactive SCHEME_BALANCED } -Message "Would set Balanced power plan (alternate)"
    }
}

Write-Status "Restore defaults finished." "SUCCESS"
Write-Status "Restart Windows to apply all changes." "WARN"

if (-not $NoPause) { Pause }
