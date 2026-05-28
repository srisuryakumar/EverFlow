# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for EverFlow.

Build commands:
  macOS:   pyinstaller --clean EverFlow.spec
  Windows: pyinstaller --clean EverFlow.spec

Output:
  macOS:   dist/EverFlow.app
  Windows: dist/EverFlow.exe
"""

import sys
import os

block_cipher = None

# Platform-specific icon paths
if sys.platform == 'darwin':
    ICON_PATH = 'assets/logo.png'
else:
    ICON_PATH = 'assets/logo.ico'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dashboard/index.html', 'dashboard'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)

if sys.platform == 'darwin':
    # macOS: Create .app bundle
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='EverFlow',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='EverFlow',
    )

    app = BUNDLE(
        coll,
        name='EverFlow.app',
        icon=ICON_PATH,
        bundle_identifier='com.everflow.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSUIElement': True,
        },
    )

elif sys.platform == 'win32':
    # Windows: Create standalone .exe
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='EverFlow',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_PATH,
    )