"""Test dell'aggiornamento dell'archivio da una versione dell'app alla nuova.

L'archivio sta sul computer di chi usa il programma ed e' l'unica copia dei
piani, delle sessioni e dello storico degli invii. Una versione nuova dell'app
deve adattarlo senza perdere niente: questi test servono a non scoprire il
contrario sul suo computer.
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import db

# Lo schema com'era prima delle colonne aggiunte al registro mail: serve a
# fabbricare un archivio "vecchio" credibile.
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


class AggiornamentoTests(unittest.TestCase):
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

    def test_archivio_nuovo_nasce_gia_aggiornato(self) -> None:
        conn = db.inizializza(self.percorso)
        versione = conn.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(versione, db.VERSIONE_SCHEMA)
        conn.close()

    def test_aggiornando_non_si_perde_niente(self) -> None:
        """Il test che conta: dati e storico devono sopravvivere."""
        self._archivio_vecchio()

        conn = db.inizializza(self.percorso)

        persona = conn.execute("SELECT * FROM persona").fetchone()
        self.assertEqual(persona["nome"], "Anna")
        self.assertEqual(persona["email"], "anna@esempio.test")

        voce = conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["oggetto"], "Convocazione")
        self.assertEqual(voce["corpo"], "testo della mail")
        self.assertEqual(voce["esito"], "inviata")
        # la colonna nuova esiste e viene riempita con quello che si sapeva
        self.assertEqual(voce["registrata_il"], "2026-01-02T10:00:00")
        conn.close()

    def test_aggiornando_si_mette_da_parte_una_copia(self) -> None:
        self._archivio_vecchio()
        conn = db.inizializza(self.percorso)
        conn.close()

        copie = list(db.cartella_copie(self.percorso).glob("*.db"))
        self.assertEqual(len(copie), 1)
        self.assertIn("aggiornamento", copie[0].name)

        # e la copia contiene davvero i dati di prima
        vecchio = sqlite3.connect(copie[0])
        self.assertEqual(
            vecchio.execute("SELECT COUNT(*) FROM mail_log").fetchone()[0], 1
        )
        vecchio.close()

    def test_riaprire_l_archivio_non_lo_tocca_di_nuovo(self) -> None:
        """Aprire l'app due volte non deve rimigrare, ne' rifare copie."""
        self._archivio_vecchio()
        db.inizializza(self.percorso).close()
        db.inizializza(self.percorso).close()

        copie = list(db.cartella_copie(self.percorso).glob("*aggiornamento*.db"))
        self.assertEqual(len(copie), 1)

        conn = db.connetti(self.percorso)
        self.assertEqual(migrate := db.migra(conn, self.percorso), [])
        self.assertEqual(migrate, [])
        conn.close()

    def test_una_migrazione_puo_essere_rieseguita_senza_danno(self) -> None:
        """Se il numero di versione si perde, riapplicarla non deve rompere."""
        self._archivio_vecchio()
        conn = db.inizializza(self.percorso)
        conn.execute("PRAGMA user_version = 0")   # come se non fosse mai girata
        conn.commit()

        db.migra(conn, self.percorso)

        voce = conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["oggetto"], "Convocazione")
        conn.close()


class CopieTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cartella = Path(tempfile.mkdtemp())
        self.percorso = self.cartella / "piano.db"
        db.inizializza(self.percorso).close()

    def tearDown(self) -> None:
        shutil.rmtree(self.cartella, ignore_errors=True)

    def test_una_copia_al_giorno_e_non_di_piu(self) -> None:
        self.assertIsNotNone(db.copia_giornaliera(self.percorso))
        self.assertIsNone(db.copia_giornaliera(self.percorso))

    def test_le_copie_vecchie_vengono_buttate(self) -> None:
        cartella = db.cartella_copie(self.percorso)
        cartella.mkdir(parents=True, exist_ok=True)
        for i in range(db.COPIE_DA_TENERE + 4):
            (cartella / f"piano-2026010{i:02d}-000000-avvio.db").write_bytes(b"")

        db.copia_archivio(self.percorso, motivo="prova")

        rimaste = list(cartella.glob("piano-*.db"))
        self.assertEqual(len(rimaste), db.COPIE_DA_TENERE)

    def test_un_archivio_inesistente_non_produce_copie(self) -> None:
        self.assertIsNone(db.copia_archivio(self.cartella / "mai-esistito.db"))


if __name__ == "__main__":
    unittest.main()
