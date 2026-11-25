# CleanUp-Pc - restore-defaults.ps1
# Reverts everything speedup.ps1 changed, using %ProgramData%\CleanUp-Pc\speedup-backup.json.
#   -NoPause   Do not wait for Enter at the end (used by the GUI).

[CmdletBinding()]
param([switch]$NoPause)

try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    if ($NoPause) { Write-Host "ERROR: Administrator rights are required."; exit 1 }
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    exit
}

$ErrorActionPreference = 'SilentlyContinue'
$GuiMode    = $NoPause.IsPresent
$BackupFile = Join-Path (Join-Path $env:ProgramData 'CleanUp-Pc') 'speedup-backup.json'

function Step {
    param([int]$Pct, [string]$Text)
    if ($GuiMode) { Write-Host "##PROGRESS:$Pct|$Text" }
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

Write-Host "Restoring settings changed by Speed Up..." -ForegroundColor Cyan

if (-not (Test-Path $BackupFile)) {
    Write-Host "No Speed Up backup was found - nothing to restore." -ForegroundColor Yellow
    if ($GuiMode) { Write-Host "##PROGRESS:100|Done" }
    Write-Host "Restore Finished Successfully!" -ForegroundColor Green
    if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
    exit 0
}

$b = Get-Content -Path $BackupFile -Raw | ConvertFrom-Json

# Power plan
Step 10 "Power plan"
$scheme = if ($b.PowerScheme) { $b.PowerScheme } else { 'SCHEME_BALANCED' }
powercfg /setactive $scheme 2>$null
if ($LASTEXITCODE -ne 0) { powercfg /setactive SCHEME_BALANCED 2>$null }
Write-Host "    Power plan restored."

# Registry values
Step 30 "Registry settings"
foreach ($r in @($b.Registry | Where-Object { $_ })) {
    if ($r.Existed) {
        if (-not (Test-Path $r.Path)) { New-Item -Path $r.Path -Force | Out-Null }
        if ($r.Kind) {
            Set-ItemProperty -Path $r.Path -Name $r.Name -Value $r.Value -Type $r.Kind -Force
        } else {
            Set-ItemProperty -Path $r.Path -Name $r.Name -Value $r.Value -Force
        }
    } else {
        Remove-ItemProperty -Path $r.Path -Name $r.Name -ErrorAction SilentlyContinue
    }
}
Write-Host "    Registry settings restored."

# Services
Step 60 "Services"
foreach ($s in @($b.Services | Where-Object { $_ })) {
    switch ([int]$s.Start) {
        2 {
            if ([int]$s.Delayed -eq 1) { sc.exe config $s.Name start= delayed-auto | Out-Null }
            else { Set-Service -Name $s.Name -StartupType Automatic }
            Start-Service -Name $s.Name -ErrorAction SilentlyContinue
        }
        3 { Set-Service -Name $s.Name -StartupType Manual }
        default { Set-Service -Name $s.Name -StartupType Manual }
    }
    Write-Host "    Restored service: $($s.Name)"
}

# Scheduled tasks
Step 85 "Scheduled tasks"
if (Get-Command Enable-ScheduledTask -ErrorAction SilentlyContinue) {
    foreach ($t in @($b.Tasks | Where-Object { $_ })) {
        Enable-ScheduledTask -TaskPath $t.Path -TaskName $t.Name -ErrorAction SilentlyContinue | Out-Null
        Write-Host "    Restored task: $($t.Name)"
    }
}

# Archive the backup so it is not applied twice
$archive = $BackupFile -replace '\.json$', ('.restored-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
Move-Item -Path $BackupFile -Destination $archive -Force

if ($GuiMode) { Write-Host "##PROGRESS:100|Done" }
Write-Host ""
Write-Host "Restore Finished Successfully!" -ForegroundColor Green
Write-Host "Restart Windows (or sign out) to fully apply the restored settings." -ForegroundColor Yellow

if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
exit 0
