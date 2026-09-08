"""Invio delle mail tramite il client di posta gia' configurato.

L'idea di partenza resta: pilotare il programma di posta che chi usa l'app ha
gia' installato e loggato. Nessuna credenziale da custodire, nessun SMTP da
farsi dare dall'IT, e la mail risulta partita dalla persona.

Due lezioni imparate provandolo davvero, che spiegano com'e' fatto questo file:

**Non si indovina il canale.** Su un Mac possono esserci Outlook e Mail, uno
configurato e l'altro no, e da fuori non si distinguono: il profilo di Outlook
puo' pesare centinaia di MB senza avere un solo account attivo. Quindi il
canale non viene dedotto, viene **scelto una volta durante la configurazione**
e salvato. `diagnosi_canali` serve a quella schermata: interroga davvero i
programmi e dice quali account hanno.

**"Nessun errore" non vuol dire "spedita".** AppleScript restituisce successo
anche quando il messaggio viene solo accodato, o quando il client lo accetta e
lo perde perche' non ha account. Registrare quella come una consegna e' il
difetto peggiore per un'applicazione che serve ad avvisare le persone: il
registro direbbe "inviata" e nessuno saprebbe mai il contrario. Per questo dopo
`send` si controlla che il messaggio **esca davvero dalla coda**, e se resta li'
e' un errore.
"""

import asyncio
import platform
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import db
from .percorsi import cartella_dati

CARTELLA_BOZZE = cartella_dati() / "dati" / "mail_non_inviate"

# Secondi di attesa perche' il client tolga il messaggio dalla coda: oltre
# questi si considera non spedito.
ATTESA_CONSEGNA = 30


class ErroreInvio(RuntimeError):
    pass


@contextmanager
def file_invito(contenuto: str | None):
    """Scrive l'invito in un file temporaneo, il tempo di allegarlo.

    I programmi di posta allegano da disco, non da memoria. Il nome del file e'
    quello che il destinatario vede: `invito.ics` si capisce.
    """
    if not contenuto:
        yield ""
        return
    cartella = Path(tempfile.mkdtemp(prefix="cicerone-"))
    percorso = cartella / "invito.ics"
    percorso.write_text(contenuto, encoding="utf-8")
    try:
        yield str(percorso)
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


def _osascript(script: str, argomenti: list[str], timeout: int = 60) -> str:
    """Esegue AppleScript passando i dati come argomenti, non nel sorgente.

    Oggetto e corpo contengono virgolette, apostrofi e a capo: incollati dentro
    lo script lo romperebbero o, peggio, si farebbero interpretare come codice.
    """
    try:
        esito = subprocess.run(
            ["osascript", "-", *argomenti],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as errore:
        raise ErroreInvio(
            "il programma di posta non ha risposto in tempo: puo' esserci una "
            "finestra aperta in attesa di risposta."
        ) from errore
    except OSError as errore:
        raise ErroreInvio(str(errore)) from errore

    if esito.returncode != 0:
        raise ErroreInvio(_spiega(esito.stderr.strip()))
    return esito.stdout.strip()


def _spiega(errore: str) -> str:
    """Traduce gli errori di osascript in qualcosa su cui si possa agire."""
    if "NESSUN_ACCOUNT" in errore:
        return (
            "il programma di posta non ha nessun account configurato: "
            "va aggiunto l'indirizzo di lavoro prima di inviare."
        )
    if "RESTA_IN_CODA" in errore:
        return (
            "il messaggio e' rimasto nella posta in uscita e non e' partito: "
            "il programma di posta non riesce a spedire (account da "
            "riautenticare, oppure offline)."
        )
    if "-1743" in errore or "not authori" in errore.lower():
        return (
            "macOS non ha concesso il permesso di controllare il programma di "
            "posta. Va abilitato in System Settings > Privacy & Security > "
            f"Automation. ({errore})"
        )
    if "-600" in errore or "-1728" in errore:
        return f"il programma di posta non risponde. ({errore})"
    return errore or "osascript non ha riportato l'errore"


class InvioOutlook:
    """Invio tramite l'Outlook installato su Windows (COM)."""

    nome = "outlook"
    etichetta = "Outlook (Windows)"

    def __init__(self, mittente: str | None = None) -> None:
        self.mittente = mittente

    def disponibile(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import win32com.client  # noqa: F401
            return True
        except ImportError:
            return False

    def account(self) -> list[str]:
        return []

    def invia(self, messaggio: dict) -> None:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # olMailItem
            mail.To = "; ".join(messaggio["destinatari"])
            mail.Subject = messaggio["oggetto"]
            mail.Body = messaggio["corpo"]
            with file_invito(messaggio.get("calendario")) as invito:
                if invito:
                    mail.Attachments.Add(invito)
                mail.Send()
        except Exception as errore:  # l'API COM non ha eccezioni tipizzate utili
            raise ErroreInvio(str(errore)) from errore
        finally:
            pythoncom.CoUninitialize()


class _InvioAppleScript:
    """Parte comune dei due programmi di posta del Mac.

    Le sottoclassi cambiano solo i due script: il dialetto AppleScript di Mail
    e quello di Outlook non coincidono.
    """

    nome = ""
    etichetta = ""
    PERCORSI: tuple[Path, ...] = ()
    SCRIPT_ACCOUNT = ""
    SCRIPT_INVIO = ""

    def __init__(self, mittente: str | None = None) -> None:
        self.mittente = mittente

    def disponibile(self) -> bool:
        """Solo la presenza del programma: e' un controllo che deve costare poco.

        Sapere se ha davvero un account richiede di interrogarlo, cioe' di
        avviarlo: si fa in `account()`, durante la configurazione, non a ogni
        caricamento della pagina.
        """
        if platform.system() != "Darwin":
            return False
        return any(percorso.exists() for percorso in self.PERCORSI)

    def account(self) -> list[str]:
        """Indirizzi utilizzabili come mittente. Avvia il programma di posta."""
        if not self.disponibile():
            return []
        try:
            uscita = _osascript(self.SCRIPT_ACCOUNT, [], timeout=60)
        except ErroreInvio:
            return []
        return [riga.strip() for riga in uscita.splitlines() if riga.strip()]

    def invia(self, messaggio: dict) -> None:
        if not messaggio["destinatari"]:
            raise ErroreInvio("nessun destinatario")
        with file_invito(messaggio.get("calendario")) as invito:
            _osascript(
                self.SCRIPT_INVIO,
                [
                    messaggio["oggetto"],
                    messaggio["corpo"],
                    self.mittente or "",
                    invito,
                    *messaggio["destinatari"],
                ],
                timeout=ATTESA_CONSEGNA + 60,
            )


class InvioMailMac(_InvioAppleScript):
    """Invio tramite Mail, l'applicazione di posta di macOS."""

    nome = "mail_mac"
    etichetta = "Mail (macOS)"

    PERCORSI = (
        Path("/System/Applications/Mail.app"),
        Path("/Applications/Mail.app"),
    )

    # Gli indirizzi si raccolgono in una lista e si uniscono alla fine:
    # concatenarli dentro il ciclo restituisce riferimenti, non testo.
    SCRIPT_ACCOUNT = """
set trovati to {}
tell application "Mail"
    repeat with a in accounts
        try
            if enabled of a then set trovati to trovati & (email addresses of a)
        end try
    end repeat
end tell
set AppleScript's text item delimiters to linefeed
return trovati as text
"""

    # `content` in Mail e' il testo semplice: i template sono file di testo.
    SCRIPT_INVIO = """
on run argv
    set oggetto to item 1 of argv
    set corpo to item 2 of argv
    set mittente to item 3 of argv
    set invito to item 4 of argv
    tell application "Mail"
        if (count of accounts) is 0 then error "NESSUN_ACCOUNT" number 1001
        if mittente is "" then
            set messaggio to make new outgoing message with properties ¬
                {subject:oggetto, content:corpo, visible:false}
        else
            set messaggio to make new outgoing message with properties ¬
                {subject:oggetto, content:corpo, sender:mittente, visible:false}
        end if
        tell messaggio
            repeat with i from 5 to (count of argv)
                make new to recipient with properties {address:(item i of argv)}
            end repeat
            if invito is not "" then
                make new attachment with properties ¬
                    {file name:(POSIX file invito)} at after the last paragraph of content
            end if
        end tell
        set identificativo to id of messaggio
        send messaggio
        -- "send" accetta il messaggio, non lo spedisce: finche' resta nella
        -- posta in uscita non e' partito niente.
        repeat ATTESA times
            delay 1
            set ancora to false
            repeat with m in (every outgoing message)
                try
                    if (id of m) is identificativo then set ancora to true
                end try
            end repeat
            if not ancora then return "spedito"
        end repeat
        error "RESTA_IN_CODA" number 1002
    end tell
end run
"""

    def __init__(self, mittente: str | None = None) -> None:
        super().__init__(mittente)
        self.SCRIPT_INVIO = self.SCRIPT_INVIO.replace("ATTESA", str(ATTESA_CONSEGNA))


class InvioOutlookMac(_InvioAppleScript):
    """Invio tramite l'Outlook installato sul Mac.

    Attenzione: le versioni recenti di Outlook per Mac hanno un supporto
    AppleScript ridotto e possono riportare zero account pur avendo un profilo
    sul disco. Per questo il conteggio degli account non e' un dettaglio ma una
    condizione: senza account il messaggio verrebbe accettato e perso.
    """

    nome = "outlook_mac"
    etichetta = "Outlook (Mac)"

    PERCORSI = (
        Path("/Applications/Microsoft Outlook.app"),
        Path.home() / "Applications" / "Microsoft Outlook.app",
    )

    SCRIPT_ACCOUNT = """
set trovati to {}
tell application "Microsoft Outlook"
    repeat with a in exchange accounts
        try
            set trovati to trovati & (email address of a)
        end try
    end repeat
    repeat with a in imap accounts
        try
            set trovati to trovati & (email address of a)
        end try
    end repeat
    repeat with a in pop accounts
        try
            set trovati to trovati & (email address of a)
        end try
    end repeat
end tell
set AppleScript's text item delimiters to linefeed
return trovati as text
"""

    # `content` in Outlook e' HTML: col testo semplice si perderebbero gli a
    # capo, quindi si usa `plain text content`.
    SCRIPT_INVIO = """
on run argv
    set oggetto to item 1 of argv
    set corpo to item 2 of argv
    set invito to item 4 of argv
    tell application "Microsoft Outlook"
        set quanti to (count of exchange accounts) + (count of imap accounts) ¬
            + (count of pop accounts)
        if quanti is 0 then error "NESSUN_ACCOUNT" number 1001
        set messaggio to make new outgoing message with properties ¬
            {subject:oggetto, plain text content:corpo}
        repeat with i from 5 to (count of argv)
            make new to recipient at messaggio with properties ¬
                {email address:{address:(item i of argv)}}
        end repeat
        if invito is not "" then
            make new attachment at messaggio with properties {file:(POSIX file invito)}
        end if
        send messaggio
        repeat ATTESA times
            delay 1
            if (count of messages of outbox) is 0 then return "spedito"
        end repeat
        error "RESTA_IN_CODA" number 1002
    end tell
end run
"""

    def __init__(self, mittente: str | None = None) -> None:
        super().__init__(mittente)
        self.SCRIPT_INVIO = self.SCRIPT_INVIO.replace("ATTESA", str(ATTESA_CONSEGNA))


class InvioSuFile:
    """Ultima possibilita': scrive la mail invece di spedirla.

    Non e' un canale di invio e non va scelto per errore: serve quando non c'e'
    nessun programma di posta, perche' il messaggio resti su disco invece di
    andare perso.
    """

    nome = "file"
    etichetta = "Salva su file (non spedisce)"

    def __init__(self, mittente: str | None = None) -> None:
        self.mittente = mittente

    def disponibile(self) -> bool:
        return True

    def account(self) -> list[str]:
        return []

    def invia(self, messaggio: dict) -> None:
        CARTELLA_BOZZE.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d-%H%M%S")
        percorso = CARTELLA_BOZZE / f"{marca}-{messaggio['tipo']}-{messaggio['sessione_id']}.txt"
        percorso.write_text(
            f"A: {'; '.join(messaggio['destinatari'])}\n"
            f"Oggetto: {messaggio['oggetto']}\n\n{messaggio['corpo']}\n",
            encoding="utf-8",
        )
        if messaggio.get("calendario"):
            percorso.with_suffix(".ics").write_text(
                messaggio["calendario"], encoding="utf-8"
            )


# In ordine di preferenza: prima i programmi di posta veri.
CANALI = (InvioOutlook, InvioMailMac, InvioOutlookMac, InvioSuFile)


def canale_per_nome(nome: str, mittente: str | None = None):
    for classe in CANALI:
        if classe.nome == nome:
            return classe(mittente)
    return None


def diagnosi_canali() -> list[dict]:
    """Cosa c'e' su questo computer, interrogandolo davvero.

    Alimenta la schermata di configurazione: elenca i programmi di posta
    presenti e gli indirizzi che hanno, cosi' la scelta la fa chi usa l'app
    invece di essere indovinata dal programma.
    """
    trovati = []
    for classe in CANALI:
        canale = classe()
        if not canale.disponibile():
            continue
        indirizzi = canale.account()
        trovati.append(
            {
                "nome": canale.nome,
                "etichetta": canale.etichetta,
                "account": indirizzi,
                "pronto": bool(indirizzi) or canale.nome in {"file", "outlook"},
            }
        )
    return trovati


def scegli_canale(conn: sqlite3.Connection | None = None):
    """Il canale da usare: quello configurato, se c'e'.

    Senza una scelta salvata si ripiega sul primo programma presente, che e'
    solo un default ragionevole: la configurazione esiste proprio perche'
    "presente" e "funzionante" non sono la stessa cosa.
    """
    if conn is not None:
        scelto = db.leggi_impostazione(conn, db.CHIAVE_CANALE_MAIL)
        if scelto:
            canale = canale_per_nome(
                scelto, db.leggi_impostazione(conn, db.CHIAVE_MITTENTE_MAIL)
            )
            if canale is not None:
                return canale

    for classe in CANALI:
        canale = classe()
        if canale.disponibile():
            return canale
    return InvioSuFile()


def _policy(
    conn: sqlite3.Connection, messaggio: dict, mail_log_id: int | None
) -> dict | None:
    """I motivi per non spedire che si decidono senza contattare nessuno."""
    from . import mail

    if not db.invio_email_automatico(conn):
        mail.registra(conn, messaggio, "invio_disattivato", mail_log_id=mail_log_id)
        return {
            "esito": "invio_disattivato",
            "senza_email": messaggio["senza_email"],
        }

    if not messaggio["destinatari"]:
        mail.registra(
            conn, messaggio, "senza_destinatari", mail_log_id=mail_log_id
        )
        return {"esito": "senza_destinatari", "senza_email": messaggio["senza_email"]}
    return None


def _registra_esito(
    conn: sqlite3.Connection,
    messaggio: dict,
    canale,
    errore: Exception | None,
    mail_log_id: int | None,
) -> dict:
    from . import mail

    if errore is not None:
        mail.registra(
            conn, messaggio, "errore", str(errore), mail_log_id=mail_log_id
        )
        return {"esito": "errore", "errore": str(errore)}

    mail.registra(conn, messaggio, "inviata", mail_log_id=mail_log_id)
    # Puo' essere partita solo a una parte dei destinatari: chi non ha
    # indirizzo va segnalato, altrimenti l'assenza passa inosservata.
    return {
        "esito": "inviata",
        "canale": canale.nome,
        "senza_email": messaggio["senza_email"],
    }


def invia(
    conn: sqlite3.Connection,
    messaggio: dict,
    mail_log_id: int | None = None,
) -> dict:
    """Applica la policy di invio, consegna se consentito e registra l'esito.

    Blocca finche' il programma di posta non ha finito. Dentro un endpoint
    usare `invia_senza_bloccare`.
    """
    bloccato = _policy(conn, messaggio, mail_log_id)
    if bloccato is not None:
        return bloccato

    canale = scegli_canale(conn)
    errore = None
    try:
        canale.invia(messaggio)
    except Exception as problema:
        errore = problema
    return _registra_esito(conn, messaggio, canale, errore, mail_log_id)


async def invia_senza_bloccare(
    conn: sqlite3.Connection,
    messaggio: dict,
    mail_log_id: int | None = None,
) -> dict:
    """Come `invia`, ma senza fermare tutta l'applicazione.

    Aspettare che il messaggio esca dalla coda puo' durare decine di secondi, e
    proprio quando qualcosa non va: dentro l'event loop l'interfaccia resterebbe
    ferma per tutto quel tempo, e chi sta compilando una sessione crederebbe che
    l'app si sia piantata. Qui la sola attesa va in un thread.

    La scrittura sul registro resta invece in questo thread: la connessione
    SQLite e' condivisa e legata all'event loop, e usarla altrove darebbe
    "SQLite objects created in a thread can only be used in that same thread".
    """
    bloccato = _policy(conn, messaggio, mail_log_id)
    if bloccato is not None:
        return bloccato

    canale = scegli_canale(conn)
    errore = None
    try:
        await asyncio.to_thread(canale.invia, messaggio)
    except Exception as problema:
        errore = problema
    return _registra_esito(conn, messaggio, canale, errore, mail_log_id)
