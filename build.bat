@echo off
setlocal

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

:: Check required files exist
for %%f in (app.py CleanUp-Pc.spec cleanup.ps1 speedup.ps1 restore-defaults.ps1 version.txt) do (
    if not exist "%%f" (
        echo ERROR: Required file missing: %%f
        echo Please ensure all project files are in this folder before building.
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

:: Done
echo.
echo [3/3] Build complete.
echo The .exe is located in: dist\CleanUp-Pc.exe
echo.
pause
