# PyInstaller spec for wabbajack-py
# Build: pyinstaller wabbajack-py.spec
# Output: dist/wabbajack-py (single file)

import sys
from pathlib import Path

block_cipher = None

# Collect all data files
datas = [
    ('src/wabbajack/web/static', 'wabbajack/web/static'),
]

# Include static dir only if it exists (built frontend)
static = Path('src/wabbajack/web/static')
if not static.exists():
    datas = []

a = Analysis(
    ['src/wabbajack/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'wabbajack.web',
        'wabbajack.web.api',
        'wabbajack.web.ws',
        'wabbajack.web.auth',
        'wabbajack.web.gallery',
        'wabbajack.downloaders',
        'wabbajack.downloaders.cdn',
        'wabbajack.downloaders.nexus',
        'wabbajack.downloaders.mediafire',
        'wabbajack.downloaders.mega',
        'wabbajack.downloaders.gdrive',
        'wabbajack.downloaders.moddb',
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
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'PIL.ImageTk'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wabbajack-py',
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
    icon=None,  # TODO: add icon
)
