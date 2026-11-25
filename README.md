# CleanUp-Pc

PowerShell cleanup and performance scripts for Windows 10, Windows 11, and Windows Server.

## Scripts

### `cleanup.ps1`

- Cleans User/Windows Temp, Prefetch, Windows Update cache, Delivery Optimization, crash logs, icon/thumbnail caches, and the Recycle Bin.
- Clears the DNS cache and restarts Explorer.
- Disables hibernation, cleans up the WinSxS component store with DISM, and compacts the OS.

### `speedup.ps1`

- Sets the High Performance power plan.
- Sets visual effects for best performance and disables transparency, background apps, and Game DVR (desktop only).
- Disables telemetry services/tasks, plus optionally SysMain, Windows Search, and Xbox services.
- Enables TRIM for SSDs, flushes DNS, and lists startup programs.
- Automatically skips client-only tweaks on Windows Server.

## Usage

Right-click the script and choose **Run with PowerShell**, or run one of these from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup.ps1
powershell -ExecutionPolicy Bypass -File .\speedup.ps1
```

Both scripts request Administrator rights automatically. Restart Windows after running `speedup.ps1`.

## Windows GUI Application (.exe)

A tkinter GUI wrapper (`app.py`) is included so you can run Cleanup or Speed up from a single window, with automatic Windows version detection (10 / 11 / Server) and automatic Administrator elevation.

### Build the .exe (on Windows)

1. Install Python (with `python` and `pip` in PATH).
2. Open PowerShell or CMD in this folder and run:

```powershell
.\build.bat
```

`build.bat` installs PyInstaller if needed, then builds a single-window executable at:

```
dist\CleanUp-Pc.exe
```

### What the app does

- Detects your Windows edition automatically (caption, build number, Desktop vs Server).
- **Cleanup My OS** — runs `cleanup.ps1` (temp files, Prefetch, Update cache, DNS, caches, Recycle Bin, hibernation, DISM, compact OS).
- **Speed Up My OS** — runs `speedup.ps1` (high-performance power plan, visual effects, services, telemetry tasks, TRIM, DNS flush, startup list).
- Skips client-only tweaks on Windows Server automatically.
- Requests Administrator rights before running either action.

## Configuration

The options block at the top of `speedup.ps1` lets you keep or disable:

| Option | Default | Effect |
| --- | --- | --- |
| `$KeepSearchIndexing` | `$true` | Set to `$false` to disable Windows Search |
| `$KeepSysMain` | `$true` | Set to `$false` to disable SysMain / Superfetch |
| `$DisableXboxServices` | `$false` | Set to `$true` to disable Xbox services |
| `$DisableTelemetry` | `$true` | Set to `$false` to keep telemetry services and tasks |

## Notes

- The High Performance plan uses more battery on laptops.
- Create a restore point before running the scripts if you want an easy rollback.
