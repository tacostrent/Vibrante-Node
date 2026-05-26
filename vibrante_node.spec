# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vibrante-Node v2.4.0 Windows 64-bit build
# Run: pyinstaller vibrante_node.spec

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# google-generativeai uses namespace packages — must collect everything
google_datas, google_binaries, google_hiddenimports = collect_all('google.generativeai')
grpc_datas, grpc_binaries, grpc_hiddenimports = collect_all('grpc')

# Collect all data files needed at runtime
datas = google_datas + grpc_datas + [
    # UI assets
    ('splash.png', '.'),
    ('logo.png', '.'),
    ('LICENSE', '.'),
    ('icons', 'icons'),
    # Node definitions
    ('nodes', 'nodes'),
    ('node_examples', 'node_examples'),
    # Houdini plugin nodes
    ('plugins/houdini/v_nodes_houdini', 'plugins/houdini/v_nodes_houdini'),
    ('plugins/houdini/v_scripts_houdini', 'plugins/houdini/v_scripts_houdini'),
    # Example workflows
    ('workflows', 'workflows'),
    # Examples
    ('examples', 'examples'),
    # HTML documentation (Help menu) + full documentation portal
    ('docs', 'docs'),
]

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=google_binaries + grpc_binaries,
    datas=datas,
    hiddenimports=google_hiddenimports + grpc_hiddenimports + collect_submodules('google') + [
        # PyQt5
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        # Google packages
        'google.generativeai',
        'google.api_core',
        'google.api_core.operations_v1',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.grpc',
        'google.auth.transport.requests',
        'google.protobuf',
        # Async
        'asyncio',
        'asyncio.events',
        # Other
        'toposort',
        'pydantic',
        # Node base
        'src.nodes.base',
        'src.core.engine',
        'src.core.graph',
        'src.core.registry',
        'src.utils.paths',
        # Prism utilities
        'src.utils.prism_core',
        'src.utils.prism_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'tkinter',
        'wx',
    ],
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
    name='Vibrante-Node',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                  # No console window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/vibrante-node-icon.png',  # App icon
    version='file_version_info.txt',      # Embeds VERSIONINFO — fixes "Unknown publisher" on Windows 11
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Vibrante-Node',
)
