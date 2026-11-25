# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("cleanup.ps1", "."),
        ("speedup.ps1", "."),
        ("restore-defaults.ps1", "."),
    ],
    hiddenimports=["settings", "diskusage"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CleanUp-Pc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX-packed exes trigger more antivirus false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version="version.txt",
    uac_admin=True,       # Windows shows the UAC prompt before the app starts
)
