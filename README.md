# CleanUp-Pc

Windows cleanup and performance optimizer for Windows 10, Windows 11, and Windows Server.

Choose **Cleanup My OS** or **Speed Up My OS** from a single Windows GUI application (.exe) that auto-detects your Windows version and elevates to Administrator automatically.

## Features

- **Auto Windows detection** — detects Windows 10, 11, or Server (caption, build number, Desktop vs Server)
- **Auto Administrator elevation** — requests elevated rights before running any action
- **Cleanup My OS** — temp files, Prefetch, Windows Update cache, Delivery Optimization, crash logs, icon/thumbnail caches, Recycle Bin, DNS cache, Explorer restart, hibernation off, DISM component cleanup, compact OS
- **Speed Up My OS** — High Performance power plan, best-performance visual effects, transparency/background apps/Game DVR off, telemetry services & tasks off, SysMain/Search/Xbox options, TRIM enable, DNS flush, startup program list
- **Server-safe** — client-only tweaks are skipped automatically on Windows Server

## Files

| File | Purpose |
|------|---------|
| `app.py` | Python tkinter GUI wrapper |
| `cleanup.ps1` | PowerShell cleanup script |
| `speedup.ps1` | PowerShell speed-up script |
| `CleanUp-Pc.spec` | PyInstaller build spec |
| `build.bat` | Windows build script to produce `CleanUp-Pc.exe` |
| `version.txt` | Version resource info for the .exe |

## Build the .exe (on Windows)

You must build on a Windows machine with Python installed.

1. Install Python (make sure `python` and `pip` are in PATH).
2. Open PowerShell or CMD in this folder.
3. Run:

```powershell
.\build.bat
```

`build.bat` installs PyInstaller if missing, then builds a single-window executable at:

```
dist\CleanUp-Pc.exe
```

## Usage

### Using the GUI (.exe)

Run `dist\CleanUp-Pc.exe` on Windows:

1. Click **Cleanup My OS** or **Speed Up My OS**.
2. Confirm the action.
3. The app elevates to Administrator and runs the matching PowerShell script, streaming output live in the log window.
4. Restart Windows after running Speed Up to apply all changes.

### Using the PowerShell scripts directly

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup.ps1
powershell -ExecutionPolicy Bypass -File .\speedup.ps1
```

Both scripts request Administrator rights automatically.

## Configuration

Edit the options block at the top of `speedup.ps1`:

| Option | Default | Effect |
|--------|---------|--------|
| `$KeepSearchIndexing` | `$true` | Set `$false` to disable Windows Search |
| `$KeepSysMain` | `$true` | Set `$false` to disable SysMain / Superfetch |
| `$DisableXboxServices` | `$false` | Set `$true` to disable Xbox services |
| `$DisableTelemetry` | `$true` | Set `$false` to keep telemetry services and tasks |

## Notes

- The High Performance power plan uses more battery on laptops.
- Create a restore point before running if you want an easy rollback.
- Run the build on Windows; PyInstaller cannot produce a Windows `.exe` from Linux.
