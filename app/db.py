"""Schema, access and upgrade of the SQLite database.

Table and column names are in Italian and stay that way: they are domain
identifiers written inside every existing archive, so renaming them here would
leave the code and the data disagreeing. The README carries a glossary.
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path

from .paths import data_folder

DB_PATH = data_folder() / "dati" / "piano.db"

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

-- Reusable catalogue: every new hire's plan is created from this.
CREATE TABLE IF NOT EXISTS modulo_catalogo (
    codice                     TEXT PRIMARY KEY,
    area                       TEXT NOT NULL,
    titolo                     TEXT NOT NULL,
    modalita_default           TEXT,
    tutor_referente_default_id INTEGER REFERENCES persona(id),
    ordine                     INTEGER NOT NULL
);

-- The colour of each training area: it is what lets you tell at a glance, in
-- the agenda and on the calendar, which field a session belongs to. The colour
-- lives on the area, so every module in it shares the same one without
-- repeating it. Missing colours are assigned at start-up by
-- rules.ensure_area_colours.
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
    -- the certification form's editable columns: these stay manual
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
    -- these identify the appointment in the recipient's calendar: they are what
    -- lets us move or cancel that one without touching the others
    uid_calendario         TEXT,
    revisione_calendario   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessione_piano ON sessione(piano_id, data);
CREATE INDEX IF NOT EXISTS idx_sessione_modulo ON sessione(piano_modulo_id);

-- A session can have several tutors: in the spreadsheet they all sat in one cell.
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
    calendario  TEXT   -- the invitation as it was sent, so it can be resent
);

CREATE TABLE IF NOT EXISTS impostazione (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);
"""

SESSION_STATES = ["Pianificata", "Confermata", "Svolta", "Rinviata", "Annullata"]
TRAINING_MODES = ["Spiegazione", "Affiancamento", "Autoapprendimento"]
CHECK_OUTCOMES = ["Superata", "Da ripetere", "N.A."]

KEY_AUTO_EMAIL = "invio_email_automatico"
# The mail program chosen during setup, and the address the notifications are
# sent from. They stay empty until setup has been done: that is how the app
# knows it has to ask on first run.
KEY_MAIL_CHANNEL = "canale_mail"
KEY_MAIL_SENDER = "mittente_mail"

# The form code printed at the top of the PDF. Every company has its own, taken
# from its quality system, and it identifies the company: that is why it lives
# in the archive rather than in the code, and is set from the training plan tab.
KEY_FORM_CODE = "codice_modulo"
DEFAULT_FORM_CODE = "MOD-FORM-01  Rev. 00"


def read_setting(
    conn: sqlite3.Connection, key: str, default: str | None = None
) -> str | None:
    """Reads a stored setting, returning the default when it is missing."""
    row = conn.execute(
        "SELECT valore FROM impostazione WHERE chiave = ?", (key,)
    ).fetchone()
    return row["valore"] if row is not None else default


def save_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Stores or updates an application setting."""
    conn.execute(
        """
        INSERT INTO impostazione (chiave, valore) VALUES (?, ?)
        ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore
        """,
        (key, value),
    )
    conn.commit()


def automatic_email_delivery(conn: sqlite3.Connection) -> bool:
    """Whether automatic delivery of notifications is switched on."""
    value = read_setting(conn, KEY_AUTO_EMAIL, "0")
    return str(value).strip().lower() in {"1", "true", "on", "si", "si'"}


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # The app is single-user and every access happens on the event loop's only
    # thread (the endpoints are async), so sharing the connection is safe.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Upgrading the app without losing anything
#
# The archive lives on the computer of whoever uses the program and holds the
# only copy of plans, sessions and delivery history: a new version of the app
# must adapt it, never recreate it. `CREATE TABLE IF NOT EXISTS` alone is not
# enough, because it does not touch tables that already exist: a column added
# to SCHEMA would not appear in an existing archive.
#
# How to add a schema change:
#
#   1. write a `_migration_N(conn)` function taking the archive from version
#      N-1 to N, moving data across if needed;
#   2. append it to MIGRATIONS with the next number.
#
# Rules: migrations are appended and never edited afterwards (they have already
# run on other people's computers), they must be safe to run twice, and they do
# not delete data. To drop a column you stop using it: that costs less than a
# table rebuild gone wrong.
# ---------------------------------------------------------------------------

BACKUPS_TO_KEEP = 10


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(
    conn: sqlite3.Connection, table: str, name: str, kind: str
) -> None:
    """A rerunnable ALTER TABLE: adds the column only when it is missing."""
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")


def _migration_1(conn: sqlite3.Connection) -> None:
    """Delivery log: when it was recorded, and who had no address."""
    _add_column(conn, "mail_log", "registrata_il", "TEXT")
    _add_column(conn, "mail_log", "senza_email", "TEXT")
    conn.execute(
        """
        UPDATE mail_log
        SET registrata_il = inviata_il
        WHERE registrata_il IS NULL AND inviata_il IS NOT NULL
        """
    )


def _migration_2(conn: sqlite3.Connection) -> None:
    """The appointment's identifier in the recipients' calendars.

    This is what allows moving or cancelling *that* particular appointment: two
    sessions between the same people carry different UIDs, so there is no risk
    of cancelling the wrong one. The sequence number must go up on every change,
    or calendars ignore the update as a duplicate.
    """
    _add_column(conn, "sessione", "uid_calendario", "TEXT")
    _add_column(
        conn, "sessione", "revisione_calendario", "INTEGER NOT NULL DEFAULT 0"
    )
    # the invitation is kept exactly as it was sent: a retry has to resend the
    # same appointment, not build a similar one
    _add_column(conn, "mail_log", "calendario", "TEXT")


# (number, what it does, function). The number ends up in `PRAGMA user_version`.
MIGRATIONS: list[tuple[int, str, object]] = [
    (1, "delivery log columns", _migration_1),
    (2, "calendar appointment identifier", _migration_2),
]

SCHEMA_VERSION = max(number for number, _, _ in MIGRATIONS) if MIGRATIONS else 0


def backup_folder(path: Path) -> Path:
    return Path(path).parent / "copie"


def backup_database(path: Path | str, reason: str = "avvio") -> Path | None:
    """Puts a copy of the archive aside before touching it.

    Uses SQLite's own backup API rather than copying the file: that stays
    consistent even while something is writing. Keeps the last
    BACKUPS_TO_KEEP copies and drops the oldest, or the folder would grow
    without end.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return None  # brand new archive: there is nothing to save

    folder = backup_folder(path)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = folder / f"{path.stem}-{stamp}-{reason}.db"

    source = sqlite3.connect(path)
    copy = sqlite3.connect(destination)
    try:
        with copy:
            source.backup(copy)
    finally:
        copy.close()
        source.close()

    existing = sorted(folder.glob(f"{path.stem}-*.db"))
    for spare in existing[:-BACKUPS_TO_KEEP]:
        spare.unlink(missing_ok=True)
    return destination


def daily_backup(path: Path | str = DB_PATH) -> Path | None:
    """One copy a day, taken at start-up.

    The archive is on no server and under no version control: if the computer
    breaks, or somebody deletes something by mistake, these copies are the only
    safety net. One a day is enough and does not fill the disk.
    """
    path = Path(path)
    today = date.today().strftime("%Y%m%d")
    existing = backup_folder(path).glob(f"{path.stem}-{today}-*.db")
    if any(existing):
        return None
    return backup_database(path, reason="avvio")


def migrate(conn: sqlite3.Connection, path: Path | str | None = None) -> list[int]:
    """Brings the archive up to date. Returns the migrations applied.

    Before changing anything it puts a copy aside: if an upgrade goes wrong, the
    data of whoever uses the program is still recoverable.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    pending = [m for m in MIGRATIONS if m[0] > version]
    if not pending:
        return []

    if path is not None:
        backup_database(path, reason="aggiornamento")

    applied = []
    for number, _description, function in pending:
        function(conn)
        conn.execute(f"PRAGMA user_version = {number}")
        applied.append(number)
    conn.commit()
    return applied


def initialise(path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = connect(path)
    brand_new = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table'"
    ).fetchone()["n"] == 0

    conn.executescript(SCHEMA)
    if brand_new:
        # A freshly created archive is already at the latest version: there is
        # nothing to migrate and no data to save.
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    else:
        migrate(conn, path)

    conn.execute(
        "INSERT OR IGNORE INTO impostazione (chiave, valore) VALUES (?, '0')",
        (KEY_AUTO_EMAIL,),
    )
    conn.commit()
    return conn
