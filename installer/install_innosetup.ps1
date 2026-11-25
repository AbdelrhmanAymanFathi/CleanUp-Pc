# installer/install_innosetup.ps1
# Installs Inno Setup 6 automatically for the CleanUp-Pc installer build.
#
# Behavior:
#   - Detects existing ISCC.exe in known paths; exits 0 if found.
#   - Tries winget (JRSoftware.InnoSetup) if available.
#   - Otherwise downloads https://jrsoftware.org/download.php/is.exe to %TEMP%.
#   - Verifies Authenticode signature (Valid, signer subject contains Jordan Russell / JRSoftware).
#   - Runs silently: /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
#     (all users if elevated, /CURRENTUSER if not).
#   - Deletes the temp installer afterwards.
#   - Exits 0 only if ISCC.exe exists in a known path after installation.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File installer\install_innosetup.ps1

$ErrorActionPreference = "Stop"

$knownPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe"
)

function Find-Iscc {
    foreach ($p in $knownPaths) {
        if (Test-Path -Path $p -PathType Leaf) {
            return $p
        }
    }
    $cmd = Get-Command -Name ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    return $null
}

# Already installed?
$existing = Find-Iscc
if ($existing) {
    Write-Host "Inno Setup 6 found at: $existing"
    exit 0
}

# Silent install flags
$installArgs = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"
$isElevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
               ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    $installArgs = "/CURRENTUSER $installArgs"
}

# --- Try winget first ---
$winget = Get-Command -Name winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host "Installing Inno Setup 6 via winget..."
    try {
        & winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
    } catch {
        Write-Host ("winget install encountered an error: " + $_.Exception.Message)
    }
    $existing = Find-Iscc
    if ($existing) {
        Write-Host ("Inno Setup 6 installed at: " + $existing)
        exit 0
    }
    Write-Host "winget did not install Inno Setup 6. Trying direct download..."
}

# --- Direct download from jrsoftware.org ---
$url = "https://jrsoftware.org/download.php/is.exe"
$tempInstaller = Join-Path $env:TEMP "innosetup-is.exe"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$maxRetries = 3
$retry = 0
$downloaded = $false
while ($retry -lt $maxRetries) {
    $retry++
    try {
        Write-Host ("Downloading Inno Setup 6 (attempt {0} of {1})..." -f $retry, $maxRetries)
        Invoke-WebRequest -Uri $url -OutFile $tempInstaller -UseBasicParsing -TimeoutSec 120
        $downloaded = $true
        break
    } catch {
        Write-Host ("Download attempt {0} failed: {1}" -f $retry, $_.Exception.Message)
        if ($retry -ge $maxRetries) {
            Write-Host "ERROR: Could not download the Inno Setup 6 installer."
            Write-Host "Please install manually from https://jrsoftware.org/isdl.php"
            if (Test-Path -Path $tempInstaller) { Remove-Item -Path $tempInstaller -Force }
            exit 1
        }
        Start-Sleep -Seconds 2
    }
}

if (-not $downloaded) {
    Write-Host "ERROR: Could not download the Inno Setup 6 installer."
    Write-Host "Please install manually from https://jrsoftware.org/isdl.php"
    exit 1
}

# --- Verify Authenticode signature ---
Write-Host "Verifying installer signature..."
try {
    $sig = Get-AuthenticodeSignature -FilePath $tempInstaller
    if ($sig.Status -ne "Valid") {
        Write-Host ("ERROR: Installer signature is not valid (status: {0})." -f $sig.Status)
        if (Test-Path -Path $tempInstaller) { Remove-Item -Path $tempInstaller -Force }
        exit 1
    }
    $cert = $sig.SignerCertificate
    if ($cert -is [array]) { $cert = $cert[0] }
    $signerSubject = $cert.Subject
    if (-not ($signerSubject -like "*Jordan Russell*" -or $signerSubject -like "*JRSoftware*")) {
        Write-Host ("ERROR: Installer signer subject does not match Jordan Russell or JRSoftware: {0}" -f $signerSubject)
        if (Test-Path -Path $tempInstaller) { Remove-Item -Path $tempInstaller -Force }
        exit 1
    }
    Write-Host ("Signature verified: " + $signerSubject)
} catch {
    Write-Host ("ERROR: Signature verification failed: " + $_.Exception.Message)
    if (Test-Path -Path $tempInstaller) { Remove-Item -Path $tempInstaller -Force }
    exit 1
}

# --- Run the installer silently ---
Write-Host "Running Inno Setup installer silently..."
$installCmd = "`"{0}`" {1}" -f $tempInstaller, $installArgs
& $installCmd
$installExitCode = $LASTEXITCODE

# Clean up the temp installer
if (Test-Path -Path $tempInstaller) { Remove-Item -Path $tempInstaller -Force }

if ($installExitCode -ne 0) {
    Write-Host ("ERROR: Inno Setup installer exited with code {0}." -f $installExitCode)
    Write-Host "Please install manually from https://jrsoftware.org/isdl.php"
    exit 1
}

# --- Verify installation ---
$existing = Find-Iscc
if ($existing) {
    Write-Host ("Inno Setup 6 installed at: " + $existing)
    exit 0
}

Write-Host "ERROR: Inno Setup 6 was not found after installation."
Write-Host "Please install manually from https://jrsoftware.org/isdl.php"
exit 1
