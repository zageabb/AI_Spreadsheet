# PyInstaller specification for the cross-platform desktop release.

import sys
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("app.formulas")

a = Analysis(
    ["app/main.py"],
    pathex=[],
    binaries=[],
    datas=[("app/services/email_templates", "app/services/email_templates")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI-Spreadsheet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AI-Spreadsheet",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="AI-Spreadsheet.app",
        icon=None,
        bundle_identifier="com.aispreadsheet.desktop",
    )
