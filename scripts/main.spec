# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for 桌面端 (PySide6 GUI).

构建::

    pyinstaller scripts/main.spec

产物：``dist/points-v2/points-v2.exe``（Windows）
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 收集 PySide6 所有子模块（PyInstaller 默认会漏一些）
hiddenimports = []
hiddenimports += collect_submodules("PySide6")
hiddenimports += collect_submodules("matplotlib")

a = Analysis(
    ["../src/points_v2/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="points-v2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI: 不开控制台
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="points-v2",
)
