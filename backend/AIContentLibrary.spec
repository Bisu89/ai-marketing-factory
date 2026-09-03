# PyInstaller build spec for the packaged desktop app.
# See docs/features/14-desktop-packaging.md for the full design.
#
# Build with:  pyinstaller AIContentLibrary.spec --noconfirm
# (run from backend/, with requirements-build.txt installed in the venv)
#
# onedir (not onefile): avoids onefile's per-launch temp-extraction delay,
# and makes the frontend/ffmpeg `datas` simple to reason about --
# app.core.config.resource_path() reads them straight out of sys._MEIPASS,
# which in onedir mode is just the app's own install folder.

import certifi

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("../frontend/dist", "frontend/dist"),
        ("../resources/ffmpeg", "resources/ffmpeg"),
        (certifi.where(), "certifi"),
    ],
    hiddenimports=[
        # uvicorn's protocol/loop implementations are selected dynamically
        # at runtime, so PyInstaller's static import scan misses them.
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # pywebview picks its Windows backend (WebView2 via pythonnet, or a
        # WinForms fallback) at runtime based on what's installed.
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "clr_loader",
        # sqlalchemy's sqlite dialect is loaded by name from database_url,
        # not a static top-level import.
        "sqlalchemy.dialects.sqlite",
        # feedparser (News module) pulls its SGML parser in dynamically --
        # the `feedparser-sgmllib` dist installs as the top-level `sgmllib`.
        "sgmllib",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIContentLibrary",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="AIContentLibrary",
)
