"""Percorsi di risorse e dati, sia in sviluppo sia dentro l'eseguibile.

PyInstaller scompatta le risorse in una cartella temporanea che sparisce alla
chiusura del programma: i dati dell'utente non possono stare li'. Quindi:

- le risorse in sola lettura (interfaccia, template originali) viaggiano
  dentro il pacchetto;
- il database, le mail e i template modificati vivono fuori, dove restano fra
  un avvio e l'altro.

Dove sia quel "fuori" dipende dal sistema, e le due convenzioni sono diverse:
su Windows accanto all'eseguibile, su macOS nella cartella dell'utente. Vedi
`cartella_dati`.
"""

import shutil
import sys
from pathlib import Path

IMPACCHETTATO = getattr(sys, "frozen", False)

NOME_APPLICAZIONE = "Cicerone"


def cartella_risorse() -> Path:
    """Dove stanno i file che il programma legge e non scrive mai."""
    if IMPACCHETTATO:
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def cartella_dati() -> Path:
    """Dove il programma scrive: mai dentro il pacchetto.

    Su macOS un `.app` e' di sola lettura per convenzione: scriverci dentro ne
    invalida la firma, e in `/Applications` il permesso spesso non c'e'
    proprio. L'archivio andrebbe a finire in
    `PianoFormazione.app/Contents/MacOS/`, che e' il posto sbagliato: sparirebbe
    a ogni aggiornamento dell'app. Su macOS quindi si usa la cartella
    dell'utente, che e' anche dove il Mac si aspetta di trovarlo.

    Su Windows invece i dati restano accanto all'eseguibile: e' il
    comportamento gia' documentato a chi usa il programma, e cambiarlo adesso
    vorrebbe dire abbandonare un archivio gia' in uso.

    In sviluppo, impacchettato o no, si resta nella cartella del progetto.
    """
    if not IMPACCHETTATO:
        return Path(__file__).resolve().parent.parent
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / NOME_APPLICAZIONE
    return Path(sys.executable).resolve().parent


def cartella_template() -> Path:
    """I template delle mail, in una cartella che l'utente puo' modificare.

    Al primo avvio dell'eseguibile vengono copiati accanto ad esso: da li'
    si aprono con il Blocco note e si cambiano i testi senza ricompilare.
    """
    destinazione = cartella_dati() / "template_mail"
    if not destinazione.exists():
        origine = cartella_risorse() / "template_mail"
        if origine.exists():
            shutil.copytree(origine, destinazione)
    return destinazione
