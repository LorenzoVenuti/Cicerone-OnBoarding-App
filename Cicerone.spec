# -*- mode: python ; coding: utf-8 -*-
"""Ricetta di PyInstaller per Cicerone.

    pyinstaller Cicerone.spec

Produce `dist/Cicerone.app` su macOS e `dist/Cicerone.exe` su Windows.
PyInstaller non compila per un sistema diverso dal proprio: ognuno dei due va
costruito sulla sua piattaforma, o dal workflow .github/workflows/.

Le due piattaforme non si impacchettano allo stesso modo. Su Windows un file
solo, che si copia e si lancia. Su macOS un `.app`, che e' una cartella con una
struttura precisa: un eseguibile unico funzionerebbe anche li', ma parte piu'
lentamente e complica la firma, quindi si usa COLLECT + BUNDLE.
"""

import sys

MACOS = sys.platform == "darwin"

# L'icona e' opzionale: senza, il pacchetto si costruisce lo stesso con quella
# di sistema. Cosi' la build non si rompe se il file non c'e' ancora.
from pathlib import Path

icona_mac = Path("app/risorse/Cicerone.icns")
icona_win = Path("app/risorse/Cicerone.ico")
ICONA = None
if MACOS and icona_mac.exists():
    ICONA = str(icona_mac)
elif not MACOS and icona_win.exists():
    ICONA = str(icona_win)

a = Analysis(
    ["avvia.py"],
    pathex=[],
    binaries=[],
    # Risorse in sola lettura: viaggiano dentro il pacchetto.
    datas=[
        ("app/web", "app/web"),
        ("template_mail", "template_mail"),
    ],
    # uvicorn e pywebview caricano pezzi di se' a runtime, quindi PyInstaller
    # non li vede analizzando gli import.
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        # la finestra nativa: WKWebView sul Mac, WinForms su Windows
        "webview.platforms.cocoa" if MACOS else "webview.platforms.winforms",
    ] + ([] if MACOS else ["win32com.client", "pythoncom"]),
    hookspath=[],
    runtime_hooks=[],
    # Fuori dal pacchetto quello che serve solo a chi sviluppa: openpyxl e'
    # dell'importazione iniziale da Excel, che si fa da riga di comando, e PIL
    # serve a crea_icona.py. Dentro peserebbero e basta.
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
        icon=ICONA,
        bundle_identifier="it.cicerone.formazione",
        info_plist={
            "CFBundleName": "Cicerone",
            "CFBundleDisplayName": "Cicerone",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            # Senza questa frase macOS nega il controllo del programma di posta
            # e le notifiche non partono: e' la spiegazione che l'utente legge
            # nella richiesta di permesso.
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
        console=False,          # niente finestra nera del terminale
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICONA,
    )
