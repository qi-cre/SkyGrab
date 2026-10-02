# -*- mode: python ; coding: utf-8 -*-
"""SkyGrab PyInstaller spec (onedir mode)."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = [
    "rich", "rich.logging",
    "textual", "textual.app", "textual.screen", "textual.css",
    "textual.message_pump", "textual.pilot", "textual.worker",
    "textual.containers",
    "textual.widgets",
    "textual.widgets.selection_list",
    "textual.widgets.progress_bar",
    "textual.widgets.rich_log",
    "pkg_resources.extern",
]

datas = []
for pkg in ("textual", "rich", "requests", "urllib3", "certifi"):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

hiddenimports += collect_submodules("textual.widgets")
hiddenimports += collect_submodules("textual.css")

a = Analysis(
    ["src/skygrab/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "PIL",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "IPython", "pytest",
        "boto3", "botocore",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="skygrab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="skygrab",
)
