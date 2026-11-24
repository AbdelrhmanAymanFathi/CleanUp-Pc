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

Clear-Host
Write-Host "Starting Full Windows Cleanup..." -ForegroundColor Cyan

# User Temp
Write-Host "Cleaning User Temp..."
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue

# Windows Temp
Write-Host "Cleaning Windows Temp..."
Remove-Item "C:\Windows\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue

# Prefetch
Write-Host "Cleaning Prefetch..."
Remove-Item "C:\Windows\Prefetch\*" -Recurse -Force -ErrorAction SilentlyContinue

# Windows Update Cache
Write-Host "Cleaning Windows Update Cache..."
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
Start-Service wuauserv

# Delivery Optimization
Write-Host "Cleaning Delivery Optimization..."
Remove-Item "C:\Windows\SoftwareDistribution\DeliveryOptimization\*" -Recurse -Force -ErrorAction SilentlyContinue

# DNS Cache
Write-Host "Clearing DNS Cache..."
Clear-DnsClientCache

# Restart Explorer
Write-Host "Refreshing Explorer..."
taskkill /f /im explorer.exe

# Icon Cache
Write-Host "Cleaning Icon Cache..."
Remove-Item "$env:LOCALAPPDATA\IconCache.db" -Force -ErrorAction SilentlyContinue

# Thumbnail Cache
Write-Host "Cleaning Thumbnail Cache..."
Remove-Item "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\thumbcache_*" -Force -ErrorAction SilentlyContinue

Start-Process explorer.exe

# Crash Logs
Write-Host "Cleaning Crash Logs..."
Remove-Item "C:\ProgramData\Microsoft\Windows\WER\*" -Recurse -Force -ErrorAction SilentlyContinue

# Recycle Bin
Write-Host "Emptying Recycle Bin..."
Clear-RecycleBin -Force -ErrorAction SilentlyContinue

# Disable Hibernate
Write-Host "Disabling Hibernate..."
powercfg /hibernate off

# DISM Cleanup
Write-Host "Running DISM Cleanup..."
DISM /Online /Cleanup-Image /StartComponentCleanup

# Compact OS
Write-Host "Compressing Windows..."
compact.exe /compactOS:always

Write-Host ""
Write-Host "Cleanup Finished Successfully!" -ForegroundColor Green
Pause