@echo off
setlocal
cd /d "%~dp0"

:: Usage: build-installer.bat [--skip-build]
::   --skip-build   reuse the existing dist\CleanUp-Pc.exe
::   Set SIGNTOOL_CMD (e.g. signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256)
::   to sign the installer and uninstaller. Do not use double quotes inside it.

echo ========================================
echo  CleanUp-Pc  -  Build installer
echo ========================================
echo.

:: Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Version check (installer vs version.txt)
echo [1/4] Checking version...
python installer\check_version.py
if %errorlevel% neq 0 (
    pause
    exit /b 1
)

:: Build the .exe
if /I "%~1"=="--skip-build" goto :checkexe

echo [2/4] Building CleanUp-Pc.exe...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install --upgrade pyinstaller
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
)
python -m PyInstaller --clean --noconfirm CleanUp-Pc.spec
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

:checkexe
if not exist "dist\CleanUp-Pc.exe" (
    echo ERROR: dist\CleanUp-Pc.exe was not found. Run without --skip-build.
    pause
    exit /b 1
)

:: Find Inno Setup compiler
echo [3/4] Looking for Inno Setup...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do set "ISCC=%%I"
if not defined ISCC (
    echo ERROR: Inno Setup 6 was not found.
    echo Install it from https://jrsoftware.org/isdl.php and run this script again.
    pause
    exit /b 1
)
echo Using: %ISCC%

:: Compile the installer
echo [4/4] Compiling installer...
if defined SIGNTOOL_CMD (
    echo Signing is ON.
    "%ISCC%" /DSIGN=1 "/Smysign=%SIGNTOOL_CMD% $f" installer\CleanUp-Pc.iss
) else (
    "%ISCC%" installer\CleanUp-Pc.iss
)
if %errorlevel% neq 0 (
    echo ERROR: Inno Setup compilation failed.
    pause
    exit /b 1
)

echo.
echo Installer created in: installer\Output\
for %%F in (installer\Output\CleanUp-Pc-Setup-*.exe) do echo   %%F
echo.
pause
