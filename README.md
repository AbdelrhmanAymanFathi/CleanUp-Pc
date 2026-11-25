# CleanUp-Pc

Windows cleanup and performance optimizer for Windows 10, Windows 11, and Windows Server.

Choose **Cleanup My OS** or **Speed Up My OS** from a single Windows GUI application (.exe) that auto-detects your Windows version and runs with Administrator rights (via UAC manifest).

## Files

| File | Purpose |
|------|---------|
| `app.py` | Python tkinter GUI wrapper |
| `cleanup.ps1` | PowerShell cleanup script |
| `speedup.ps1` | PowerShell speed-up script |
| `restore-defaults.ps1` | PowerShell script to revert Speed Up changes |
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

`build.bat` checks that all required files exist, installs PyInstaller if needed, then builds a single-window executable at:

```
dist\CleanUp-Pc.exe
```

## Using the GUI (.exe)

Run `dist\CleanUp-Pc.exe` on Windows. The app requests Administrator rights automatically via its UAC manifest.

### Main actions

- **Cleanup My OS** — removes temp files, caches, logs, and (optionally) browser caches, Windows.old, .chk files, old Event Logs, Prefetch, hibernation, and compact OS. Measures and reports freed disk space.
- **Speed Up My OS** — applies High Performance power plan, visual-effects tweaks, service tuning, telemetry task disabling, DNS flush, and lists startup programs. Creates a restore point first (Desktop only).
- **Auto Optimize (Recommended)** — runs Cleanup then Speed Up (Windows 10/11). On Windows Server, runs Cleanup only (client tweaks skipped).
- **Undo Speed Up** — reverts Speed Up changes: re-enables services, scheduled tasks, registry values, and sets the power plan back to Balanced.
- **Scan only / dry run** — reports what would be removed and how much space would be freed, without deleting anything.
- **Cancel** — kills the running PowerShell process tree.
- **Save log to file** — exports the log output.

### Options (checkboxes in the GUI)

Cleanup tab:
- Standard (ON by default): User Temp, Windows Temp, Windows Update cache, Delivery Optimization, DNS cache, Icon cache, Thumbnail cache, Crash logs, Recycle Bin
- Optional (OFF by default): Prefetch, Disable hibernation, Compact OS, Chrome cache, Edge cache, Firefox cache, Windows.old, .chk files, Old Event Logs

Speed Up tab:
- Keep Windows Search indexing (default ON)
- Keep SysMain / Superfetch (default ON)
- Disable Xbox services (default OFF)
- Disable telemetry (default ON)

Startup Programs tab:
- Refresh the list, check items, then click **Disable Selected** to remove them from startup.

### Windows detection

The app detects your Windows edition (10 / 11 / Server) using `sys.getwindowsversion()` and the registry `ProductName`. Build >= 22000 is treated as Windows 11. Client-only tweaks are skipped automatically on Windows Server.

## Using the PowerShell scripts directly

All scripts accept a `-NoPause` switch (used by the GUI) and common boolean parameters. Run from an elevated PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup.ps1
powershell -ExecutionPolicy Bypass -File .\speedup.ps1
powershell -ExecutionPolicy Bypass -File .\restore-defaults.ps1
```

Example with parameters:

```powershell
.\cleanup.ps1 -NoPause -CleanPrefetch:$true -CompactOS:$true -CleanChromeCache:$true
.\speedup.ps1 -NoPause -KeepSearchIndexing:$false -DisableTelemetry:$true
```

## Notes

- The High Performance power plan uses more battery on laptops.
- Create a restore point before running if you want an easy rollback (Speed Up does this automatically on Desktop).
- Run the build on Windows; PyInstaller cannot produce a Windows `.exe` from Linux.
- The .exe is built with `upx=False` to reduce antivirus false positives and `uac_admin=True` for automatic elevation.
