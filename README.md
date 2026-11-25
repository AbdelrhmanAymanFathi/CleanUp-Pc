# CleanUp-Pc

Windows cleanup and performance optimizer for Windows 10, Windows 11, and Windows Server.

One GUI application (.exe) that detects your Windows version, asks for Administrator rights through UAC, and lets you choose exactly what to clean or tune.

## Features

- **Reliable Windows detection** — Windows 10, 11 or Server, build number and Desktop/Server edition (read from the registry, no PowerShell needed)
- **UAC elevation built into the .exe** — Windows asks for Administrator rights before the app starts
- **Cleanup My OS** — temp files, Windows Update cache, Delivery Optimization, crash reports, thumbnails, Recycle Bin, DNS cache. Optional: browser caches, Windows.old, DISM component cleanup, Prefetch, Hibernate off, Explorer restart + icon cache, event logs, Compact OS
- **Scan only (dry run)** — shows how much space each item would free without deleting anything
- **Freed space report** — free space before/after cleanup
- **Speed Up My OS** — High Performance power plan, best-performance visual effects, transparency/background apps/Game DVR off, tips off, telemetry services & tasks off, optional SysMain / Search / Xbox changes. A restore point is created first (Desktop)
- **Undo Speed Up** — every change is recorded and can be reverted exactly
- **Startup Manager** — enable/disable startup programs from the GUI
- **Progress bar, Cancel, Save log**
- **Server-safe** — client-only tweaks are skipped automatically on Windows Server

All options are checkboxes in the GUI. Risky items (Compact OS, Prefetch, Hibernate off, event logs, Explorer restart) are **off by default**.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Python tkinter GUI |
| `cleanup.ps1` | Cleanup script (also usable standalone) |
| `speedup.ps1` | Speed-up script (also usable standalone) |
| `restore-defaults.ps1` | Reverts what `speedup.ps1` changed |
| `CleanUp-Pc.spec` | PyInstaller build spec (`uac_admin=True`, UPX off) |
| `build.bat` | Windows build script that produces `CleanUp-Pc.exe` |
| `version.txt` | Version resource info for the .exe |

## Build the .exe (on Windows)

1. Install Python (`python` must be in PATH).
2. Open PowerShell or CMD in this folder and run:

```powershell
.\build.bat
```

The result is `dist\CleanUp-Pc.exe`. PyInstaller cannot produce a Windows `.exe` from Linux.

## Usage

### GUI

Run `dist\CleanUp-Pc.exe` (accept the UAC prompt), tick the options you want, then:

- **Scan only** — preview what Cleanup would remove
- **Cleanup My OS** / **Speed Up My OS** — run one action
- **Auto Optimize** — Windows 10/11: Cleanup then Speed Up. Server: Cleanup only
- **Undo Speed Up** — restore the settings Speed Up changed
- **Startup Manager** — toggle startup programs

Restart Windows after Speed Up to apply everything.

### PowerShell scripts directly

Each script re-launches itself as Administrator and keeps the window open at the end.

```powershell
# Cleanup (safe defaults), preview first
powershell -ExecutionPolicy Bypass -File .\cleanup.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File .\cleanup.ps1 -BrowserCache -RunDism

# Speed up, then undo
powershell -ExecutionPolicy Bypass -File .\speedup.ps1 -DisableSysMain
powershell -ExecutionPolicy Bypass -File .\restore-defaults.ps1
```

#### cleanup.ps1 switches

| Switch | Effect |
|--------|--------|
| `-DryRun` | Measure only, delete nothing |
| `-BrowserCache` | Chrome / Edge / Brave / Firefox caches |
| `-RunDism` | DISM component store cleanup |
| `-WindowsOld` | Remove Windows.old |
| `-CleanPrefetch` | Delete Prefetch |
| `-DisableHibernate` | `powercfg /hibernate off` (also disables Fast Startup) |
| `-RestartExplorer` | Restart Explorer and rebuild the icon cache |
| `-EventLogs` | Clear all event logs |
| `-CompactOS` | `compact /compactOS:always` |
| `-NoPause` | Do not wait for Enter at the end |

#### speedup.ps1 switches

| Switch | Effect |
|--------|--------|
| `-KeepTelemetry` | Keep telemetry services and tasks |
| `-DisableSysMain` | Disable SysMain / Superfetch |
| `-DisableSearch` | Disable Windows Search |
| `-DisableXbox` | Disable Xbox services |
| `-NoRestorePoint` | Skip the restore point |
| `-NoPause` | Do not wait for Enter at the end |

## Notes

- The High Performance power plan uses more battery on laptops.
- Undo data is stored in `%ProgramData%\CleanUp-Pc\speedup-backup.json`.
- Per-user registry tweaks apply to the account that runs the app.
- Antivirus tools can be suspicious of unsigned system-tuning .exe files; code signing reduces this.
