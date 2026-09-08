"""Schema, accesso e aggiornamento del database SQLite."""

import sqlite3
from datetime import date, datetime
from pathlib import Path

from .percorsi import cartella_dati

PERCORSO_DB = cartella_dati() / "dati" / "piano.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS persona (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL,
    cognome       TEXT NOT NULL,
    email         TEXT,
    reparto       TEXT,
    attivo        INTEGER NOT NULL DEFAULT 1,
    UNIQUE (nome, cognome)
);

CREATE TABLE IF NOT EXISTS risorsa (
    id                  INTEGER PRIMARY KEY,
    persona_id          INTEGER NOT NULL REFERENCES persona(id),
    reparto             TEXT,
    mansione            TEXT,
    responsabile_id     INTEGER REFERENCES persona(id),
    tutor_principale_id INTEGER REFERENCES persona(id),
    data_inizio         TEXT,
    motivo              TEXT
);

-- Catalogo riutilizzabile: da qui nasce il piano di ogni nuovo assunto.
CREATE TABLE IF NOT EXISTS modulo_catalogo (
    codice                     TEXT PRIMARY KEY,
    area                       TEXT NOT NULL,
    titolo                     TEXT NOT NULL,
    modalita_default           TEXT,
    tutor_referente_default_id INTEGER REFERENCES persona(id),
    ordine                     INTEGER NOT NULL
);

-- Colore di ogni area formativa: serve a riconoscere a colpo d'occhio, in
-- agenda e sul calendario, di che ambito e' una sessione (Commerciale, IT,
-- Ufficio Tecnico...). Il colore sta sull'area, cosi' tutti i moduli della
-- stessa area lo condividono senza doverlo ripetere. I colori mancanti vengono
-- assegnati all'avvio da regole.assicura_colori_aree.
CREATE TABLE IF NOT EXISTS area (
    nome   TEXT PRIMARY KEY,
    colore TEXT NOT NULL,
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS piano (
    id         INTEGER PRIMARY KEY,
    risorsa_id INTEGER NOT NULL REFERENCES risorsa(id),
    creato_il  TEXT NOT NULL,
    chiuso_il  TEXT
);

CREATE TABLE IF NOT EXISTS piano_modulo (
    id                 INTEGER PRIMARY KEY,
    piano_id           INTEGER NOT NULL REFERENCES piano(id) ON DELETE CASCADE,
    codice             TEXT NOT NULL,
    area               TEXT NOT NULL,
    titolo             TEXT NOT NULL,
    applicabile        TEXT NOT NULL DEFAULT 'SI',
    modalita           TEXT,
    tutor_referente_id INTEGER REFERENCES persona(id),
    ordine             INTEGER NOT NULL,
    -- colonne gialle del documento ISO: restano manuali
    entro_il           TEXT,
    verifica_chiusura  TEXT,
    verifica_efficacia TEXT,
    data_verifica      TEXT,
    esito              TEXT,
    UNIQUE (piano_id, codice)
);

CREATE TABLE IF NOT EXISTS sessione (
    id                     INTEGER PRIMARY KEY,
    piano_id               INTEGER NOT NULL REFERENCES piano(id) ON DELETE CASCADE,
    piano_modulo_id        INTEGER REFERENCES piano_modulo(id),
    data                   TEXT NOT NULL,
    ora_inizio             TEXT NOT NULL,
    ora_fine               TEXT NOT NULL,
    dettaglio              TEXT,
    stato                  TEXT NOT NULL DEFAULT 'Pianificata',
    esito_verifica         TEXT,
    note                   TEXT,
    chiusa_automaticamente INTEGER NOT NULL DEFAULT 0,
    sostituisce_id         INTEGER REFERENCES sessione(id),
    creata_il              TEXT NOT NULL,
    modificata_il          TEXT NOT NULL,
    -- identificano l'appuntamento nel calendario di chi lo riceve: servono a
    -- spostare o disdire proprio quello, senza toccare gli altri
    uid_calendario         TEXT,
    revisione_calendario   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessione_piano ON sessione(piano_id, data);
CREATE INDEX IF NOT EXISTS idx_sessione_modulo ON sessione(piano_modulo_id);

-- Una sessione puo' avere piu' tutor: nell'Excel stavano tutti in una cella.
CREATE TABLE IF NOT EXISTS sessione_tutor (
    sessione_id INTEGER NOT NULL REFERENCES sessione(id) ON DELETE CASCADE,
    persona_id  INTEGER NOT NULL REFERENCES persona(id),
    PRIMARY KEY (sessione_id, persona_id)
);

CREATE TABLE IF NOT EXISTS mail_log (
    id          INTEGER PRIMARY KEY,
    sessione_id INTEGER REFERENCES sessione(id) ON DELETE SET NULL,
    tipo        TEXT NOT NULL,
    destinatari TEXT NOT NULL,
    oggetto     TEXT NOT NULL,
    corpo       TEXT NOT NULL,
    registrata_il TEXT,
    inviata_il  TEXT,
    esito       TEXT NOT NULL,
    errore      TEXT,
    senza_email TEXT,
    calendario  TEXT   -- l'invito com'e' stato spedito, per poterlo rimandare
);

CREATE TABLE IF NOT EXISTS impostazione (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);
"""

STATI_SESSIONE = ["Pianificata", "Confermata", "Svolta", "Rinviata", "Annullata"]
MODALITA = ["Spiegazione", "Affiancamento", "Autoapprendimento"]
ESITI_VERIFICA = ["Superata", "Da ripetere", "N.A."]
CHIAVE_INVIO_EMAIL_AUTOMATICO = "invio_email_automatico"
# Il programma di posta scelto in configurazione, e l'indirizzo da cui parte la
# notifica. Restano vuoti finche' la configurazione non e' stata fatta: e' cosi'
# che l'app sa di doverla chiedere al primo avvio.
CHIAVE_CANALE_MAIL = "canale_mail"
CHIAVE_MITTENTE_MAIL = "mittente_mail"

# Il codice del modulo stampato in testa al PDF. Ogni azienda ha il suo, preso
# dal proprio sistema qualita', e dice di quale azienda si tratta: per questo
# non sta nel codice ma nell'archivio, e si imposta dalla scheda Piano ISO.
CHIAVE_CODICE_MODULO = "codice_modulo"
CODICE_MODULO_PREDEFINITO = "MOD-FORM-01  Rev. 00"


def leggi_impostazione(
    conn: sqlite3.Connection, chiave: str, predefinito: str | None = None
) -> str | None:
    """Legge un'impostazione persistita, restituendo il default se assente."""
    riga = conn.execute(
        "SELECT valore FROM impostazione WHERE chiave = ?", (chiave,)
    ).fetchone()
    return riga["valore"] if riga is not None else predefinito


def salva_impostazione(conn: sqlite3.Connection, chiave: str, valore: str) -> None:
    """Salva o aggiorna un'impostazione applicativa."""
    conn.execute(
        """
        INSERT INTO impostazione (chiave, valore) VALUES (?, ?)
        ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore
        """,
        (chiave, valore),
    )
    conn.commit()


def invio_email_automatico(conn: sqlite3.Connection) -> bool:
    """Restituisce se la consegna automatica delle email è abilitata."""
    valore = leggi_impostazione(
        conn, CHIAVE_INVIO_EMAIL_AUTOMATICO, "0"
    )
    return str(valore).strip().lower() in {"1", "true", "on", "si", "sì"}


def connetti(percorso: Path | str = PERCORSO_DB) -> sqlite3.Connection:
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    # L'app e' monoutente e tutti gli accessi avvengono nell'unico thread
    # dell'event loop (gli endpoint sono async), quindi condividere la
    # connessione e' sicuro.
    conn = sqlite3.connect(percorso, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Aggiornare l'app senza perdere niente
#
# L'archivio vive sul computer di chi usa il programma e contiene l'unica copia
# di piani, sessioni e storico degli invii: una nuova versione dell'app deve
# adattarlo, mai ricrearlo. `CREATE TABLE IF NOT EXISTS` da solo non basta,
# perche' non tocca le tabelle che esistono gia': una colonna aggiunta allo
# SCHEMA non comparirebbe su un archivio esistente.
#
# Come si aggiunge una modifica allo schema:
#
#   1. si scrive una funzione `_migrazione_N(conn)` che porta l'archivio dalla
#      versione N-1 alla N, spostando i dati se serve;
#   2. la si aggiunge in fondo a MIGRAZIONI con il numero successivo.
#
# Regole: le migrazioni si aggiungono in fondo e non si modificano piu' (sono
# gia' girate sui computer altrui), vanno scritte in modo da poter essere
# rieseguite senza danno, e non cancellano dati. Per togliere una colonna si
# smette di usarla: costa meno di una ricostruzione della tabella andata male.
# ---------------------------------------------------------------------------

COPIE_DA_TENERE = 10


def _colonne(conn: sqlite3.Connection, tabella: str) -> set[str]:
    return {riga["name"] for riga in conn.execute(f"PRAGMA table_info({tabella})")}


def _aggiungi_colonna(
    conn: sqlite3.Connection, tabella: str, nome: str, tipo: str
) -> None:
    """ALTER TABLE che si puo' rieseguire: aggiunge la colonna solo se manca."""
    if nome not in _colonne(conn, tabella):
        conn.execute(f"ALTER TABLE {tabella} ADD COLUMN {nome} {tipo}")


def _migrazione_1(conn: sqlite3.Connection) -> None:
    """Registro mail: quando e' stata registrata, e chi era senza indirizzo."""
    _aggiungi_colonna(conn, "mail_log", "registrata_il", "TEXT")
    _aggiungi_colonna(conn, "mail_log", "senza_email", "TEXT")
    conn.execute(
        """
        UPDATE mail_log
        SET registrata_il = inviata_il
        WHERE registrata_il IS NULL AND inviata_il IS NOT NULL
        """
    )


def _migrazione_2(conn: sqlite3.Connection) -> None:
    """Identificativo dell'appuntamento nel calendario dei destinatari.

    Serve a poter spostare o disdire *quel* preciso appuntamento: due sessioni
    fra le stesse persone hanno UID diversi, quindi non si rischia di
    cancellare quella sbagliata. La revisione va alzata a ogni modifica, o i
    calendari ignorano l'aggiornamento come se fosse un doppione.
    """
    _aggiungi_colonna(conn, "sessione", "uid_calendario", "TEXT")
    _aggiungi_colonna(
        conn, "sessione", "revisione_calendario", "INTEGER NOT NULL DEFAULT 0"
    )
    # l'invito viene conservato com'e' stato spedito: un "riprova" deve
    # rimandare lo stesso appuntamento, non ricostruirne uno simile
    _aggiungi_colonna(conn, "mail_log", "calendario", "TEXT")


# (numero, cosa fa, funzione). Il numero finisce in `PRAGMA user_version`.
MIGRAZIONI: list[tuple[int, str, object]] = [
    (1, "colonne del registro mail", _migrazione_1),
    (2, "identificativo dell'appuntamento in calendario", _migrazione_2),
]

VERSIONE_SCHEMA = max(numero for numero, _, _ in MIGRAZIONI) if MIGRAZIONI else 0


def cartella_copie(percorso: Path) -> Path:
    return Path(percorso).parent / "copie"


def copia_archivio(percorso: Path | str, motivo: str = "avvio") -> Path | None:
    """Mette da parte una copia dell'archivio prima di toccarlo.

    Usa l'API di backup di SQLite invece di copiare il file: e' consistente
    anche se qualcuno sta scrivendo. Tiene le ultime COPIE_DA_TENERE e butta le
    piu' vecchie, altrimenti la cartella cresce senza fine.
    """
    percorso = Path(percorso)
    if not percorso.exists() or percorso.stat().st_size == 0:
        return None  # archivio nuovo: non c'e' niente da salvare

    cartella = cartella_copie(percorso)
    cartella.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    destinazione = cartella / f"{percorso.stem}-{marca}-{motivo}.db"

    origine = sqlite3.connect(percorso)
    copia = sqlite3.connect(destinazione)
    try:
        with copia:
            origine.backup(copia)
    finally:
        copia.close()
        origine.close()

    vecchie = sorted(cartella.glob(f"{percorso.stem}-*.db"))
    for superflua in vecchie[:-COPIE_DA_TENERE]:
        superflua.unlink(missing_ok=True)
    return destinazione


def copia_giornaliera(percorso: Path | str = PERCORSO_DB) -> Path | None:
    """Una copia al giorno, fatta all'avvio.

    L'archivio non e' su nessun server e non e' versionato: se il computer si
    rompe o qualcuno cancella una cosa per sbaglio, queste copie sono l'unica
    rete. Una al giorno basta e non riempie il disco.
    """
    percorso = Path(percorso)
    oggi = date.today().strftime("%Y%m%d")
    esistenti = cartella_copie(percorso).glob(f"{percorso.stem}-{oggi}-*.db")
    if any(esistenti):
        return None
    return copia_archivio(percorso, motivo="avvio")


def migra(conn: sqlite3.Connection, percorso: Path | str | None = None) -> list[int]:
    """Porta l'archivio all'ultima versione. Restituisce le migrazioni applicate.

    Prima di modificare qualcosa mette da parte una copia: se un aggiornamento
    va storto, i dati di chi usa il programma sono ancora recuperabili.
    """
    versione = conn.execute("PRAGMA user_version").fetchone()[0]
    da_applicare = [m for m in MIGRAZIONI if m[0] > versione]
    if not da_applicare:
        return []

    if percorso is not None:
        copia_archivio(percorso, motivo="aggiornamento")

    applicate = []
    for numero, _descrizione, funzione in da_applicare:
        funzione(conn)
        conn.execute(f"PRAGMA user_version = {numero}")
        applicate.append(numero)
    conn.commit()
    return applicate


def inizializza(percorso: Path | str = PERCORSO_DB) -> sqlite3.Connection:
    conn = connetti(percorso)
    nuovo = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table'"
    ).fetchone()["n"] == 0

    conn.executescript(SCHEMA)
    if nuovo:
        # Archivio appena creato: e' gia' all'ultima versione, non c'e' niente
        # da migrare e nessun dato da salvare.
        conn.execute(f"PRAGMA user_version = {VERSIONE_SCHEMA}")
    else:
        migra(conn, percorso)

    conn.execute(
        "INSERT OR IGNORE INTO impostazione (chiave, valore) VALUES (?, '0')",
        (CHIAVE_INVIO_EMAIL_AUTOMATICO,),
    )
    conn.commit()
    return conn
