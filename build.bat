@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo  CleanUp-Pc  -  Build Windows .exe
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Check that every file the build needs is present
for %%F in (app.py cleanup.ps1 speedup.ps1 restore-defaults.ps1 CleanUp-Pc.spec version.txt) do (
    if not exist "%%F" (
        echo ERROR: Missing required file: %%F
        pause
        exit /b 1
    )
)

:: Install PyInstaller if missing
echo [1/3] Checking PyInstaller...
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

:: Build the executable
echo [2/3] Building CleanUp-Pc.exe with PyInstaller...
python -m PyInstaller --clean --noconfirm CleanUp-Pc.spec
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

if not exist "dist\CleanUp-Pc.exe" (
    echo ERROR: Build finished but dist\CleanUp-Pc.exe was not found.
    pause
    exit /b 1
)

:: Done
echo.
echo [3/3] Build complete.
echo The .exe is located in: dist\CleanUp-Pc.exe
echo.
pause
