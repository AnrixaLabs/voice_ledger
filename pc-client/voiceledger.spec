# Build with: pyinstaller voiceledger.spec
# Output: dist/VoiceLedger.exe (Windows only - see pc-client/README.md
# for why this can't be produced from Linux/macOS).
#
# winsdk (Windows Runtime bindings, used by biometric_windows.py) does
# a lot of its module loading dynamically, which PyInstaller's static
# import scanner can miss - hence the explicit hiddenimports below
# rather than relying on auto-detection.
from PyInstaller.utils.hooks import collect_submodules

hidden = (
    collect_submodules("winsdk")
    + [
        "winsdk.windows.security.credentials",
        "winsdk.windows.security.cryptography.core",
        "winsdk.windows.storage.streams",
    ]
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
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
    a.binaries,
    a.datas,
    [],
    name="VoiceLedger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app - no terminal window
    onefile=True,
)
