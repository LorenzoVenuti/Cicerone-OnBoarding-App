# -*- mode: python ; coding: utf-8 -*-
"""The PyInstaller recipe for Cicerone.

    pyinstaller Cicerone.spec

Produces `dist/Cicerone.app` on macOS and `dist/Cicerone.exe` on Windows.
PyInstaller does not cross-compile: each package is built on its own platform,
or by the workflows in .github/workflows/.

The two platforms are not packaged the same way. On Windows, a single file to
copy and launch. On macOS a `.app`, which is a folder with a precise structure:
a single executable would work there too, but it starts more slowly and makes
signing harder, so COLLECT + BUNDLE is used instead.
"""

import sys

MACOS = sys.platform == "darwin"

# The icon is optional: without it the package is still built, with the system
# one. That way the build does not break when the file is not there yet.
from pathlib import Path

icon_mac = Path("app/resources/Cicerone.icns")
icon_win = Path("app/resources/Cicerone.ico")
ICON = None
if MACOS and icon_mac.exists():
    ICON = str(icon_mac)
elif not MACOS and icon_win.exists():
    ICON = str(icon_win)

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    # Read-only resources: they travel inside the package.
    datas=[
        ("app/web", "app/web"),
        ("template_mail", "template_mail"),
    ],
    # uvicorn and pywebview load parts of themselves at runtime, so PyInstaller
    # does not see them when it analyses the imports.
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        # the native window: WKWebView on the Mac, WinForms on Windows
        "webview.platforms.cocoa" if MACOS else "webview.platforms.winforms",
    ] + ([] if MACOS else ["win32com.client", "pythoncom"]),
    hookspath=[],
    runtime_hooks=[],
    # Left out of the package: what only a developer needs. openpyxl belongs to
    # the initial spreadsheet import, run from the command line, and PIL to
    # make_icon.py. Inside, they would only add weight.
    excludes=["openpyxl", "PIL", "tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

if MACOS:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Cicerone",
        debug=False,
        strip=False,
        upx=False,
        console=False,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="Cicerone"
    )
    app = BUNDLE(
        coll,
        name="Cicerone.app",
        icon=ICON,
        bundle_identifier="it.cicerone.formazione",
        info_plist={
            "CFBundleName": "Cicerone",
            "CFBundleDisplayName": "Cicerone",
            "CFBundleShortVersionString": "1.1.0",
            "CFBundleVersion": "1.1.0",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            # Without this sentence macOS denies control of the mail program
            # and no notification goes out: it is the explanation the user
            # reads in the permission prompt, so it stays in Italian.
            "NSAppleEventsUsageDescription":
                "Cicerone usa il tuo programma di posta per inviare le "
                "notifiche e gli inviti in calendario delle sessioni di "
                "formazione.",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Cicerone",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,          # no black terminal window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )
