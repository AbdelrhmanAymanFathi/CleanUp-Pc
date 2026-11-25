@echo off
setlocal

:: Usage: build-installer.bat [--skip-build] [--yes] [--no-install]
::   --skip-build   reuse the existing dist\CleanUp-Pc.exe
::   --yes          skip confirmation prompts (CI mode)
::   --no-install   if Inno Setup 6 is missing, print the old error and exit
::   Set SIGNTOOL_CMD (e.g. signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256)
::   to sign the installer and uninstaller. Do not use double quotes inside it.

set "FORCE_YES=0"
set "NO_INSTALL=0"
set "SKIP_BUILD=0"

for %%A in (%*) do (
    if /I "%%A"=="--skip-build" set "SKIP_BUILD=1"
    if /I "%%A"=="--yes" set "FORCE_YES=1"
    if /I "%%A"=="--no-install" set "NO_INSTALL=1"
)

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
if %SKIP_BUILD% equ 1 goto :checkexe

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
call :find_iscc
if "%ISCC%"=="" (
    if %NO_INSTALL% equ 1 (
        echo ERROR: Inno Setup 6 was not found.
        echo Install it from https://jrsoftware.org/isdl.php and run this script again.
        pause
        exit /b 1
    )
    echo Inno Setup 6 is missing and will be downloaded and installed.
    if %FORCE_YES% equ 0 (
        echo.
        set "CONFIRM="
        set /p "CONFIRM=Proceed? (Y/n): "
        if /I "%CONFIRM%"=="N" (
            echo Aborted by user.
            pause
            exit /b 1
        )
    )
    powershell -NoProfile -ExecutionPolicy Bypass -File "installer\install_innosetup.ps1"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install Inno Setup 6.
        echo Please install manually from https://jrsoftware.org/isdl.php and run this script again.
        pause
        exit /b 1
    )
    echo Re-checking for Inno Setup 6...
    call :find_iscc
    if "%ISCC%"=="" (
        echo ERROR: Inno Setup 6 still was not found after installation.
        echo Please install manually from https://jrsoftware.org/isdl.php and run this script again.
        pause
        exit /b 1
    )
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
goto :eof

:find_iscc
set "ISCC="
rem Avoid the %ProgramFiles(x86)% batch pitfall in parenthesized blocks;
rem keep these as single-line statements outside of any ( ... ) block.
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do set "ISCC=%%I"
goto :eof
