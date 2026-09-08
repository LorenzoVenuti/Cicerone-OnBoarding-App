"""Tests for upgrading the archive from one version of the app to the next.

The archive sits on the computer of whoever uses the program and is the only
copy of the plans, the sessions and the delivery history. A new version has to
adapt it without losing anything: these tests exist so nobody discovers the
opposite on that computer.
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import db

# The schema as it was before the delivery-log columns were added: used to
# build a believable "old" archive.
SCHEMA_VECCHIO = """
CREATE TABLE persona (
    id INTEGER PRIMARY KEY, nome TEXT NOT NULL, cognome TEXT NOT NULL,
    email TEXT, reparto TEXT, attivo INTEGER NOT NULL DEFAULT 1,
    UNIQUE (nome, cognome)
);
CREATE TABLE mail_log (
    id INTEGER PRIMARY KEY, sessione_id INTEGER, tipo TEXT NOT NULL,
    destinatari TEXT NOT NULL, oggetto TEXT NOT NULL, corpo TEXT NOT NULL,
    inviata_il TEXT, esito TEXT NOT NULL, errore TEXT
);
CREATE TABLE impostazione (chiave TEXT PRIMARY KEY, valore TEXT);
"""


class UpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cartella = Path(tempfile.mkdtemp())
        self.percorso = self.cartella / "piano.db"

    def tearDown(self) -> None:
        shutil.rmtree(self.cartella, ignore_errors=True)

    def _archivio_vecchio(self) -> None:
        """Un archivio come lo lascerebbe la versione precedente dell'app."""
        conn = sqlite3.connect(self.percorso)
        conn.executescript(SCHEMA_VECCHIO)
        conn.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Anna', 'Bianchi', 'anna@esempio.test')"
        )
        conn.execute(
            """INSERT INTO mail_log (sessione_id, tipo, destinatari, oggetto, corpo,
                                     inviata_il, esito)
               VALUES (7, 'nuova', 'anna@esempio.test', 'Convocazione',
                       'testo della mail', '2026-01-02T10:00:00', 'inviata')"""
        )
        conn.commit()
        conn.close()

    def test_a_new_archive_is_born_up_to_date(self) -> None:
        conn = db.initialise(self.percorso)
        versione = conn.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(versione, db.SCHEMA_VERSION)
        conn.close()

    def test_upgrading_loses_nothing(self) -> None:
        """The one that matters: data and history must survive."""
        self._archivio_vecchio()

        conn = db.initialise(self.percorso)

        persona = conn.execute("SELECT * FROM persona").fetchone()
        self.assertEqual(persona["nome"], "Anna")
        self.assertEqual(persona["email"], "anna@esempio.test")

        voce = conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["oggetto"], "Convocazione")
        self.assertEqual(voce["corpo"], "testo della mail")
        self.assertEqual(voce["esito"], "inviata")
        # the new column exists and is filled with what was already known
        self.assertEqual(voce["registrata_il"], "2026-01-02T10:00:00")
        conn.close()

    def test_upgrading_puts_a_copy_aside(self) -> None:
        self._archivio_vecchio()
        conn = db.initialise(self.percorso)
        conn.close()

        copie = list(db.backup_folder(self.percorso).glob("*.db"))
        self.assertEqual(len(copie), 1)
        self.assertIn("aggiornamento", copie[0].name)

        # and the copy really does hold the earlier data
        vecchio = sqlite3.connect(copie[0])
        self.assertEqual(
            vecchio.execute("SELECT COUNT(*) FROM mail_log").fetchone()[0], 1
        )
        vecchio.close()

    def test_reopening_the_archive_does_not_touch_it_again(self) -> None:
        """Opening the app twice must not migrate again, nor copy again."""
        self._archivio_vecchio()
        db.initialise(self.percorso).close()
        db.initialise(self.percorso).close()

        copie = list(db.backup_folder(self.percorso).glob("*aggiornamento*.db"))
        self.assertEqual(len(copie), 1)

        conn = db.connect(self.percorso)
        self.assertEqual(migrate := db.migrate(conn, self.percorso), [])
        self.assertEqual(migrate, [])
        conn.close()

    def test_a_migration_can_be_rerun_safely(self) -> None:
        """If the version number is lost, reapplying must not break anything."""
        self._archivio_vecchio()
        conn = db.initialise(self.percorso)
        conn.execute("PRAGMA user_version = 0")   # as if it had never run
        conn.commit()

        db.migrate(conn, self.percorso)

        voce = conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["oggetto"], "Convocazione")
        conn.close()


class BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cartella = Path(tempfile.mkdtemp())
        self.percorso = self.cartella / "piano.db"
        db.initialise(self.percorso).close()

    def tearDown(self) -> None:
        shutil.rmtree(self.cartella, ignore_errors=True)

    def test_one_backup_a_day_and_no_more(self) -> None:
        self.assertIsNotNone(db.daily_backup(self.percorso))
        self.assertIsNone(db.daily_backup(self.percorso))

    def test_old_backups_are_discarded(self) -> None:
        cartella = db.backup_folder(self.percorso)
        cartella.mkdir(parents=True, exist_ok=True)
        for i in range(db.BACKUPS_TO_KEEP + 4):
            (cartella / f"piano-2026010{i:02d}-000000-avvio.db").write_bytes(b"")

        db.backup_database(self.percorso, reason="prova")

        rimaste = list(cartella.glob("piano-*.db"))
        self.assertEqual(len(rimaste), db.BACKUPS_TO_KEEP)

    def test_a_missing_archive_produces_no_backup(self) -> None:
        self.assertIsNone(db.backup_database(self.cartella / "mai-esistito.db"))


if __name__ == "__main__":
    unittest.main()
