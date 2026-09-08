"""Test automatici per policy e registro delle notifiche email."""

import asyncio
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import db, invio, mail


class MockSender:
    """Sender sintetico che registra le consegne senza inviare email."""

    nome = "mock"

    def __init__(self, errore: Exception | None = None) -> None:
        self.chiamate: list[dict] = []
        self.errore = errore

    def invia(self, messaggio: dict) -> None:
        self.chiamate.append(messaggio)
        if self.errore is not None:
            raise self.errore


def crea_fixture(conn: sqlite3.Connection) -> dict[str, int]:
    """Crea un piano sintetico con una risorsa e due tutor."""
    persone = [
        ("Mario", "Rossi", "mario@example.test", "Produzione"),
        ("Andrea", "Bianchi", "andrea@example.test", "Produzione"),
        ("Luca", "Verdi", "luca@example.test", "Produzione"),
    ]
    ids: dict[str, int] = {}
    for persona in persone:
        ids[persona[1]] = conn.execute(
            "INSERT INTO persona (nome,cognome,email,reparto) VALUES (?,?,?,?)",
            persona,
        ).lastrowid
    risorsa = conn.execute(
        "INSERT INTO risorsa (persona_id,reparto,mansione,data_inizio) VALUES (?,?,?,?)",
        (ids["Rossi"], "Produzione", "Operatore", "2026-09-01"),
    ).lastrowid
    piano = conn.execute(
        "INSERT INTO piano (risorsa_id,creato_il) VALUES (?,?)",
        (risorsa, "2026-09-01T08:00:00"),
    ).lastrowid
    modulo = conn.execute(
        """
        INSERT INTO piano_modulo
            (piano_id,codice,area,titolo,applicabile,modalita,ordine)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (piano, "M01", "Area A", "Modulo sintetico", "SI", "Aula", 1),
    ).lastrowid
    sessione = conn.execute(
        """
        INSERT INTO sessione
            (piano_id,piano_modulo_id,data,ora_inizio,ora_fine,dettaglio,
             stato,creata_il,modificata_il)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (piano, modulo, "2026-09-07", "09:00", "10:00", "Coaching sintetico",
         "Pianificata", "2026-09-07T08:00:00", "2026-09-07T08:00:00"),
    ).lastrowid
    conn.executemany(
        "INSERT INTO sessione_tutor (sessione_id,persona_id) VALUES (?,?)",
        [(sessione, ids["Bianchi"]), (sessione, ids["Verdi"])],
    )
    conn.commit()
    return {"piano": piano, "modulo": modulo, "sessione": sessione, **ids}


class EmailSafetyCoreTests(unittest.TestCase):
    """Verifica policy, destinatari, log e retry senza API o GUI."""

    def setUp(self) -> None:
        self.cartella = Path(tempfile.mkdtemp(prefix="pipeline-email-test-"))
        self.conn = db.inizializza(self.cartella / "piano.db")
        self.fixture = crea_fixture(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def messaggio(self, tipo: str) -> dict:
        precedente = (
            {"data": "2026-09-07", "ora_inizio": "09:00", "ora_fine": "10:00"}
            if tipo == "spostamento" else None
        )
        return mail.componi(self.conn, self.fixture["sessione"], tipo, precedente)

    def test_default_off_blocca_tutti_i_trigger_e_scrive_il_log(self) -> None:
        sender = MockSender()
        with patch.object(invio, "scegli_canale", return_value=sender) as scegli_canale:
            risultati = [
                invio.invia(self.conn, self.messaggio(tipo))
                for tipo in ("nuova", "spostamento", "annullamento")
            ]

        self.assertFalse(db.invio_email_automatico(self.conn))
        scegli_canale.assert_not_called()
        self.assertEqual([], sender.chiamate)
        self.assertEqual(
            ["invio_disattivato", "invio_disattivato", "invio_disattivato"],
            [r["esito"] for r in risultati],
        )
        righe = self.conn.execute(
            "SELECT tipo, destinatari, oggetto, corpo, esito, senza_email, "
            "registrata_il, inviata_il FROM mail_log ORDER BY id"
        ).fetchall()
        self.assertEqual(3, len(righe))
        self.assertEqual(["nuova", "spostamento", "annullamento"], [r["tipo"] for r in righe])
        self.assertTrue(all(r["oggetto"] and r["corpo"] for r in righe))
        self.assertTrue(all(r["esito"] == "invio_disattivato" for r in righe))
        self.assertTrue(all(r["registrata_il"] for r in righe))
        self.assertTrue(all(r["inviata_il"] is None for r in righe))

    def test_toggle_on_invia_e_destinatari_sono_risorsa_e_tutti_i_tutor(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        sender = MockSender()
        with patch.object(invio, "scegli_canale", return_value=sender):
            risultato = invio.invia(self.conn, self.messaggio("nuova"))

        self.assertEqual("inviata", risultato["esito"])
        self.assertEqual(1, len(sender.chiamate))
        self.assertEqual(
            ["andrea@example.test", "luca@example.test", "mario@example.test"],
            sender.chiamate[0]["destinatari"],
        )
        self.assertEqual("inviata", self.conn.execute(
            "SELECT esito FROM mail_log ORDER BY id DESC LIMIT 1"
        ).fetchone()["esito"])

    def test_deduplicazione_case_insensitive_preserva_lordine(self) -> None:
        self.conn.execute(
            "UPDATE persona SET email = ? WHERE cognome = ?",
            ("MARIO@example.test", "Bianchi"),
        )
        self.conn.commit()
        destinatari = mail.componi(
            self.conn, self.fixture["sessione"], "nuova"
        )["destinatari"]
        self.assertEqual(["MARIO@example.test", "luca@example.test"], destinatari)

    def test_email_con_spazi_e_mancante(self) -> None:
        self.conn.execute(
            "UPDATE persona SET email = ? WHERE cognome IN (?, ?)",
            ("   ", "Verdi", "Rossi"),
        )
        self.conn.commit()
        messaggio = mail.componi(self.conn, self.fixture["sessione"], "nuova")
        self.assertEqual(["andrea@example.test"], messaggio["destinatari"])
        self.assertEqual(["Luca Verdi", "Mario Rossi"], messaggio["senza_email"])

    def test_senza_destinatari_non_chiama_sender(self) -> None:
        self.conn.execute("UPDATE persona SET email = ?", ("   ",))
        self.conn.commit()
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        sender = MockSender()
        messaggio = self.messaggio("nuova")
        with patch.object(invio, "scegli_canale", return_value=sender) as scegli_canale:
            risultato = invio.invia(self.conn, messaggio)
        self.assertEqual("senza_destinatari", risultato["esito"])
        self.assertEqual([], sender.chiamate)
        scegli_canale.assert_not_called()
        riga = self.conn.execute(
            "SELECT esito, senza_email FROM mail_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual("senza_destinatari", riga["esito"])
        self.assertIn("Mario Rossi", riga["senza_email"])

    def test_senza_email_viene_persistito_nel_log(self) -> None:
        self.conn.execute(
            "UPDATE persona SET email = NULL WHERE cognome = ?", ("Verdi",)
        )
        self.conn.commit()
        invio.invia(self.conn, self.messaggio("nuova"))
        voce = mail.voce_log(self.conn.execute("SELECT * FROM mail_log").fetchone())
        self.assertEqual(["Luca Verdi"], voce["senza_email"])

    def test_persistenza_toggle_tra_connessioni(self) -> None:
        percorso = self.cartella / "piano.db"
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        self.conn.close()
        self.conn = db.inizializza(percorso)
        self.assertTrue(db.invio_email_automatico(self.conn))
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "0")
        self.conn.close()
        self.conn = db.inizializza(percorso)
        self.assertFalse(db.invio_email_automatico(self.conn))

    def test_retry_off_aggiorna_la_stessa_voce_senza_sender(self) -> None:
        sender = MockSender()
        with patch.object(invio, "scegli_canale", return_value=sender):
            messaggio = self.messaggio("nuova")
            invio.invia(self.conn, messaggio)
            voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
            risultato = invio.invia(
                self.conn, mail.messaggio_da_log(voce), mail_log_id=voce["id"]
            )
        self.assertEqual("invio_disattivato", risultato["esito"])
        self.assertEqual([], sender.chiamate)
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) c FROM mail_log").fetchone()[0])

    def test_retry_on_success_e_errore_aggiornano_la_voce(self) -> None:
        messaggio = self.messaggio("nuova")
        invio.invia(self.conn, messaggio)
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        registrata_originale = voce["registrata_il"]
        self.assertIsNotNone(registrata_originale)
        messaggio_salvato = mail.messaggio_da_log(voce)
        sender = MockSender()
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        with patch.object(invio, "scegli_canale", return_value=sender):
            risultato = invio.invia(
                self.conn, messaggio_salvato, mail_log_id=voce["id"]
            )
        self.assertEqual("inviata", risultato["esito"])
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) c FROM mail_log").fetchone()[0])
        aggiornata = self.conn.execute(
            "SELECT registrata_il, inviata_il FROM mail_log WHERE id = ?", (voce["id"],)
        ).fetchone()
        self.assertEqual(registrata_originale, aggiornata["registrata_il"])
        self.assertIsNotNone(aggiornata["inviata_il"])
        self.assertEqual(messaggio_salvato["destinatari"], sender.chiamate[0]["destinatari"])
        self.assertEqual(messaggio_salvato["oggetto"], sender.chiamate[0]["oggetto"])
        self.assertEqual(messaggio_salvato["corpo"], sender.chiamate[0]["corpo"])

        sender_errore = MockSender(invio.ErroreInvio("errore sintetico"))
        with patch.object(invio, "scegli_canale", return_value=sender_errore):
            risultato = invio.invia(
                self.conn,
                mail.messaggio_da_log(self.conn.execute("SELECT * FROM mail_log").fetchone()),
                mail_log_id=voce["id"],
            )
        self.assertEqual("errore", risultato["esito"])
        aggiornato = self.conn.execute(
            "SELECT esito, errore, registrata_il, inviata_il FROM mail_log WHERE id = ?",
            (voce["id"],),
        ).fetchone()
        self.assertEqual("errore", aggiornato["esito"])
        self.assertEqual("errore sintetico", aggiornato["errore"])
        self.assertEqual(registrata_originale, aggiornato["registrata_il"])
        self.assertIsNone(aggiornato["inviata_il"])

    def test_invii_riusciti_registrano_entrambi_i_timestamp(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        sender = MockSender()
        with patch.object(invio, "scegli_canale", return_value=sender):
            invio.invia(self.conn, self.messaggio("nuova"))
        riga = self.conn.execute("SELECT registrata_il, inviata_il FROM mail_log").fetchone()
        self.assertIsNotNone(riga["registrata_il"])
        self.assertIsNotNone(riga["inviata_il"])

    def test_errore_registra_solo_timestamp_di_registrazione(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        sender = MockSender(invio.ErroreInvio("errore sintetico"))
        with patch.object(invio, "scegli_canale", return_value=sender):
            risultato = invio.invia(self.conn, self.messaggio("nuova"))
        self.assertEqual("errore", risultato["esito"])
        riga = self.conn.execute(
            "SELECT registrata_il, inviata_il FROM mail_log"
        ).fetchone()
        self.assertIsNotNone(riga["registrata_il"])
        self.assertIsNone(riga["inviata_il"])


class EmailMigrationTests(unittest.TestCase):
    """Verifica la migrazione idempotente del registro email."""

    def test_migrazione_legacy_preserva_dati_e_default_off(self) -> None:
        cartella = Path(tempfile.mkdtemp(prefix="pipeline-email-migration-test-"))
        percorso = cartella / "piano.db"
        conn_legacy = sqlite3.connect(percorso)
        conn_legacy.execute(
            """
            CREATE TABLE mail_log (
                id INTEGER PRIMARY KEY,
                sessione_id INTEGER,
                tipo TEXT NOT NULL,
                destinatari TEXT NOT NULL,
                oggetto TEXT NOT NULL,
                corpo TEXT NOT NULL,
                inviata_il TEXT,
                esito TEXT NOT NULL,
                errore TEXT
            )
            """
        )
        conn_legacy.execute(
            """
            INSERT INTO mail_log
                (tipo, destinatari, oggetto, corpo, inviata_il, esito)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("nuova", "a@example.test", "Oggetto", "Corpo",
             "2026-09-07T10:00:00", "inviata"),
        )
        conn_legacy.commit()
        conn_legacy.close()
        try:
            conn = db.inizializza(percorso)
            colonne = {
                riga["name"] for riga in conn.execute("PRAGMA table_info(mail_log)")
            }
            riga = conn.execute("SELECT * FROM mail_log").fetchone()
            self.assertIn("senza_email", colonne)
            self.assertIn("registrata_il", colonne)
            self.assertEqual("2026-09-07T10:00:00", riga["registrata_il"])
            self.assertEqual("Oggetto", riga["oggetto"])
            self.assertFalse(db.invio_email_automatico(conn))
            conn.close()

            conn = db.inizializza(percorso)
            colonne_seconda = {
                riga["name"] for riga in conn.execute("PRAGMA table_info(mail_log)")
            }
            self.assertEqual(colonne, colonne_seconda)
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM mail_log").fetchone()[0])
            conn.close()
        finally:
            shutil.rmtree(cartella, ignore_errors=True)


class EmailApiTests(unittest.TestCase):
    """Verifica i trigger API e le operazioni del registro su DB temporaneo."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cartella = Path(tempfile.mkdtemp(prefix="pipeline-email-api-test-"))
        originale = db.inizializza
        db.inizializza = lambda percorso=db.PERCORSO_DB: originale(cls.cartella / "piano.db")
        try:
            from app import main
        finally:
            db.inizializza = originale
        cls.main = main

    def setUp(self) -> None:
        self.conn = db.inizializza(self.cartella / f"test-{id(self)}.db")
        self.main.conn = self.conn
        self.fixture = crea_fixture(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.cartella, ignore_errors=True)

    def test_endpoint_trigger_nuova_spostamento_annullamento_con_off(self) -> None:
        sender = MockSender()
        dati = self.main.SessioneIn(
            piano_id=self.fixture["piano"], piano_modulo_id=self.fixture["modulo"],
            data="2026-09-08", ora_inizio="10:00", ora_fine="11:00",
            dettaglio="Nuovo coaching",
            tutor=[self.fixture["Bianchi"], self.fixture["Verdi"]],
        )
        with patch.object(invio, "scegli_canale", return_value=sender):
            creata = asyncio.run(self.main.crea_sessione(dati))
            spostata = asyncio.run(self.main.modifica_sessione(
                creata["id"], self.main.SessionePatch(data="2026-09-09")
            ))
            annullata = asyncio.run(self.main.annulla_sessione(creata["id"]))
        self.assertEqual("invio_disattivato", creata["mail"]["esito"])
        self.assertEqual("invio_disattivato", spostata["mail"]["esito"])
        self.assertEqual("invio_disattivato", annullata["mail"]["esito"])
        self.assertEqual([], sender.chiamate)

    def test_api_retry_off_on_e_delete_non_tocca_la_sessione(self) -> None:
        messaggio = mail.componi(self.conn, self.fixture["sessione"], "nuova")
        invio.invia(self.conn, messaggio)
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        registro = asyncio.run(self.main.registro_mail())
        self.assertIn("registrata_il", registro[0])
        retry_off = asyncio.run(self.main.riprova_mail(voce["id"]))
        self.assertEqual("invio_disattivato", retry_off["esito"])

        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        sender = MockSender()
        with patch.object(invio, "scegli_canale", return_value=sender):
            retry_on = asyncio.run(self.main.riprova_mail(voce["id"]))
        self.assertEqual("inviata", retry_on["esito"])
        self.assertEqual(1, len(sender.chiamate))

        asyncio.run(self.main.elimina_mail(voce["id"]))
        self.assertIsNotNone(self.conn.execute(
            "SELECT id FROM sessione WHERE id = ?", (self.fixture["sessione"],)
        ).fetchone())
        self.assertIsNotNone(self.conn.execute(
            "SELECT id FROM piano WHERE id = ?", (self.fixture["piano"],)
        ).fetchone())
        self.assertIsNone(self.conn.execute(
            "SELECT id FROM mail_log WHERE id = ?", (voce["id"],)
        ).fetchone())

    def test_api_retry_e_delete_inesistenti_restituiscono_404(self) -> None:
        with self.assertRaises(HTTPException) as retry_error:
            asyncio.run(self.main.riprova_mail(999999))
        self.assertEqual(404, retry_error.exception.status_code)

        with self.assertRaises(HTTPException) as delete_error:
            asyncio.run(self.main.elimina_mail(999999))
        self.assertEqual(404, delete_error.exception.status_code)

    def test_api_retry_di_mail_inviata_restituisce_409(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        sender = MockSender()
        with patch.object(invio, "scegli_canale", return_value=sender):
            invio.invia(self.conn, mail.componi(
                self.conn, self.fixture["sessione"], "nuova"
            ))
        voce = self.conn.execute("SELECT id FROM mail_log").fetchone()
        with self.assertRaises(HTTPException) as errore:
            asyncio.run(self.main.riprova_mail(voce["id"]))
        self.assertEqual(409, errore.exception.status_code)

    def test_api_impostazioni_persistono(self) -> None:
        iniziale = asyncio.run(self.main.impostazioni_mail())
        self.assertFalse(iniziale["invio_email_automatico"])
        attivata = asyncio.run(self.main.salva_impostazioni_mail(
            self.main.ImpostazioneMailIn(invio_email_automatico=True)
        ))
        self.assertTrue(attivata["invio_email_automatico"])
        persistita = asyncio.run(self.main.impostazioni_mail())
        self.assertTrue(persistita["invio_email_automatico"])


if __name__ == "__main__":
    unittest.main()
