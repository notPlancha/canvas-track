# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Canvas Track standalone Windows executable."""

from pathlib import Path

block_cipher = None

# Hidden imports required by FastAPI, Uvicorn, Typer, and Pydantic
hidden_imports = [
    "canvas_track",
    "canvas_track.cli",
    "canvas_track.client",
    "canvas_track.models",
    "canvas_track.moodle_client",
    "canvas_track.moodle_rewriter",
    "canvas_track.moodle_sync",
    "canvas_track.protocol",
    "canvas_track.rewriter",
    "canvas_track.server",
    "canvas_track.sync",
    "canvas_track.sync_manager",
    "canvas_track.vault",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "multipart",
    "python_multipart",
    "dotenv",
    "rich",
    "rich.table",
    "rich.progress",
    "rich.console",
    "typer",
    "pydantic",
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.middleware.cors",
]

# Static assets from frontend build
datas = [
    ("src/canvas_track/static", "canvas_track/static"),
]

a = Analysis(
    ["src/canvas_track/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="canvas-track",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
