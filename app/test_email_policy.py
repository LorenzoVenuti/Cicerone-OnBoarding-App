"""Tests for the delivery policy and the notification log."""

import asyncio
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import db, delivery, messages


class MockSender:
    """A stand-in sender that records deliveries without sending anything."""

    name = "mock"

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def send(self, message: dict) -> None:
        self.calls.append(message)
        if self.error is not None:
            raise self.error


def make_fixture(conn: sqlite3.Connection) -> dict[str, int]:
    """Creates a synthetic plan with one trainee and two tutors."""
    people = [
        ("Mario", "Rossi", "mario@example.test", "Produzione"),
        ("Andrea", "Bianchi", "andrea@example.test", "Produzione"),
        ("Luca", "Verdi", "luca@example.test", "Produzione"),
    ]
    ids: dict[str, int] = {}
    for person in people:
        ids[person[1]] = conn.execute(
            "INSERT INTO persona (nome,cognome,email,reparto) VALUES (?,?,?,?)",
            person,
        ).lastrowid
    trainee = conn.execute(
        "INSERT INTO risorsa (persona_id,reparto,mansione,data_inizio) VALUES (?,?,?,?)",
        (ids["Rossi"], "Produzione", "Operatore", "2026-09-01"),
    ).lastrowid
    plan = conn.execute(
        "INSERT INTO piano (risorsa_id,creato_il) VALUES (?,?)",
        (trainee, "2026-09-01T08:00:00"),
    ).lastrowid
    module = conn.execute(
        """
        INSERT INTO piano_modulo
            (piano_id,codice,area,titolo,applicabile,modalita,ordine)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (plan, "M01", "Area A", "Modulo sintetico", "SI", "Aula", 1),
    ).lastrowid
    session = conn.execute(
        """
        INSERT INTO sessione
            (piano_id,piano_modulo_id,data,ora_inizio,ora_fine,dettaglio,
             stato,creata_il,modificata_il)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (plan, module, "2026-09-07", "09:00", "10:00", "Coaching sintetico",
         "Pianificata", "2026-09-07T08:00:00", "2026-09-07T08:00:00"),
    ).lastrowid
    conn.executemany(
        "INSERT INTO sessione_tutor (sessione_id,persona_id) VALUES (?,?)",
        [(session, ids["Bianchi"]), (session, ids["Verdi"])],
    )
    conn.commit()
    return {"piano": plan, "modulo": module, "sessione": session, **ids}


class DeliveryPolicyTests(unittest.TestCase):
    """Checks the policy, the recipients, the log and the retry, with no API or GUI."""

    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix="cicerone-email-test-"))
        self.conn = db.initialise(self.folder / "piano.db")
        self.fixture = make_fixture(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.folder, ignore_errors=True)

    def message(self, kind: str) -> dict:
        previous = (
            {"data": "2026-09-07", "ora_inizio": "09:00", "ora_fine": "10:00"}
            if kind == "spostamento" else None
        )
        return messages.compose(self.conn, self.fixture["sessione"], kind, previous)

    def test_default_off_blocks_every_trigger_and_still_logs(self) -> None:
        sender = MockSender()
        with patch.object(delivery, "choose_channel", return_value=sender) as choose_channel_mock:
            results = [
                delivery.send(self.conn, self.message(kind))
                for kind in ("nuova", "spostamento", "annullamento")
            ]

        self.assertFalse(db.automatic_email_delivery(self.conn))
        choose_channel_mock.assert_not_called()
        self.assertEqual([], sender.calls)
        self.assertEqual(
            ["invio_disattivato", "invio_disattivato", "invio_disattivato"],
            [r["esito"] for r in results],
        )
        rows = self.conn.execute(
            "SELECT tipo, destinatari, oggetto, corpo, esito, senza_email, "
            "registrata_il, inviata_il FROM mail_log ORDER BY id"
        ).fetchall()
        self.assertEqual(3, len(rows))
        self.assertEqual(["nuova", "spostamento", "annullamento"], [r["tipo"] for r in rows])
        self.assertTrue(all(r["oggetto"] and r["corpo"] for r in rows))
        self.assertTrue(all(r["esito"] == "invio_disattivato" for r in rows))
        self.assertTrue(all(r["registrata_il"] for r in rows))
        self.assertTrue(all(r["inviata_il"] is None for r in rows))

    def test_with_delivery_on_it_sends_to_trainee_and_all_tutors(self) -> None:
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        sender = MockSender()
        with patch.object(delivery, "choose_channel", return_value=sender):
            result = delivery.send(self.conn, self.message("nuova"))

        self.assertEqual("inviata", result["esito"])
        self.assertEqual(1, len(sender.calls))
        self.assertEqual(
            ["andrea@example.test", "luca@example.test", "mario@example.test"],
            sender.calls[0]["destinatari"],
        )
        self.assertEqual("inviata", self.conn.execute(
            "SELECT esito FROM mail_log ORDER BY id DESC LIMIT 1"
        ).fetchone()["esito"])

    def test_deduplication_is_case_insensitive_and_keeps_order(self) -> None:
        self.conn.execute(
            "UPDATE persona SET email = ? WHERE cognome = ?",
            ("MARIO@example.test", "Bianchi"),
        )
        self.conn.commit()
        destinatari = messages.compose(
            self.conn, self.fixture["sessione"], "nuova"
        )["destinatari"]
        self.assertEqual(["MARIO@example.test", "luca@example.test"], destinatari)

    def test_blank_and_missing_addresses(self) -> None:
        self.conn.execute(
            "UPDATE persona SET email = ? WHERE cognome IN (?, ?)",
            ("   ", "Verdi", "Rossi"),
        )
        self.conn.commit()
        message = messages.compose(self.conn, self.fixture["sessione"], "nuova")
        self.assertEqual(["andrea@example.test"], message["destinatari"])
        self.assertEqual(["Luca Verdi", "Mario Rossi"], message["senza_email"])

    def test_no_recipients_means_no_sender_call(self) -> None:
        self.conn.execute("UPDATE persona SET email = ?", ("   ",))
        self.conn.commit()
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        sender = MockSender()
        message = self.message("nuova")
        with patch.object(delivery, "choose_channel", return_value=sender) as choose_channel_mock:
            result = delivery.send(self.conn, message)
        self.assertEqual("senza_destinatari", result["esito"])
        self.assertEqual([], sender.calls)
        choose_channel_mock.assert_not_called()
        row = self.conn.execute(
            "SELECT esito, senza_email FROM mail_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual("senza_destinatari", row["esito"])
        self.assertIn("Mario Rossi", row["senza_email"])

    def test_missing_addresses_are_stored_in_the_log(self) -> None:
        self.conn.execute(
            "UPDATE persona SET email = NULL WHERE cognome = ?", ("Verdi",)
        )
        self.conn.commit()
        delivery.send(self.conn, self.message("nuova"))
        voce = messages.log_entry(self.conn.execute("SELECT * FROM mail_log").fetchone())
        self.assertEqual(["Luca Verdi"], voce["senza_email"])

    def test_the_toggle_persists_across_connections(self) -> None:
        path = self.folder / "piano.db"
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        self.conn.close()
        self.conn = db.initialise(path)
        self.assertTrue(db.automatic_email_delivery(self.conn))
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "0")
        self.conn.close()
        self.conn = db.initialise(path)
        self.assertFalse(db.automatic_email_delivery(self.conn))

    def test_retry_with_delivery_off_updates_the_same_entry(self) -> None:
        sender = MockSender()
        with patch.object(delivery, "choose_channel", return_value=sender):
            message = self.message("nuova")
            delivery.send(self.conn, message)
            voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
            result = delivery.send(
                self.conn, messages.message_from_log(voce), mail_log_id=voce["id"]
            )
        self.assertEqual("invio_disattivato", result["esito"])
        self.assertEqual([], sender.calls)
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) c FROM mail_log").fetchone()[0])

    def test_retry_updates_the_entry_on_success_and_failure(self) -> None:
        message = self.message("nuova")
        delivery.send(self.conn, message)
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        registrata_originale = voce["registrata_il"]
        self.assertIsNotNone(registrata_originale)
        messaggio_salvato = messages.message_from_log(voce)
        sender = MockSender()
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        with patch.object(delivery, "choose_channel", return_value=sender):
            result = delivery.send(
                self.conn, messaggio_salvato, mail_log_id=voce["id"]
            )
        self.assertEqual("inviata", result["esito"])
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) c FROM mail_log").fetchone()[0])
        aggiornata = self.conn.execute(
            "SELECT registrata_il, inviata_il FROM mail_log WHERE id = ?", (voce["id"],)
        ).fetchone()
        self.assertEqual(registrata_originale, aggiornata["registrata_il"])
        self.assertIsNotNone(aggiornata["inviata_il"])
        self.assertEqual(messaggio_salvato["destinatari"], sender.calls[0]["destinatari"])
        self.assertEqual(messaggio_salvato["oggetto"], sender.calls[0]["oggetto"])
        self.assertEqual(messaggio_salvato["corpo"], sender.calls[0]["corpo"])

        sender_errore = MockSender(delivery.DeliveryError("errore sintetico"))
        with patch.object(delivery, "choose_channel", return_value=sender_errore):
            result = delivery.send(
                self.conn,
                messages.message_from_log(self.conn.execute("SELECT * FROM mail_log").fetchone()),
                mail_log_id=voce["id"],
            )
        self.assertEqual("errore", result["esito"])
        aggiornato = self.conn.execute(
            "SELECT esito, errore, registrata_il, inviata_il FROM mail_log WHERE id = ?",
            (voce["id"],),
        ).fetchone()
        self.assertEqual("errore", aggiornato["esito"])
        self.assertEqual("errore sintetico", aggiornato["errore"])
        self.assertEqual(registrata_originale, aggiornato["registrata_il"])
        self.assertIsNone(aggiornato["inviata_il"])

    def test_successful_delivery_records_both_timestamps(self) -> None:
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        sender = MockSender()
        with patch.object(delivery, "choose_channel", return_value=sender):
            delivery.send(self.conn, self.message("nuova"))
        row = self.conn.execute("SELECT registrata_il, inviata_il FROM mail_log").fetchone()
        self.assertIsNotNone(row["registrata_il"])
        self.assertIsNotNone(row["inviata_il"])

    def test_a_failure_records_only_the_logged_timestamp(self) -> None:
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        sender = MockSender(delivery.DeliveryError("errore sintetico"))
        with patch.object(delivery, "choose_channel", return_value=sender):
            result = delivery.send(self.conn, self.message("nuova"))
        self.assertEqual("errore", result["esito"])
        row = self.conn.execute(
            "SELECT registrata_il, inviata_il FROM mail_log"
        ).fetchone()
        self.assertIsNotNone(row["registrata_il"])
        self.assertIsNone(row["inviata_il"])


class MigrationTests(unittest.TestCase):
    """Checks that the mail log migration is idempotent."""

    def test_legacy_migration_keeps_data_and_defaults_to_off(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="cicerone-email-migration-test-"))
        path = folder / "piano.db"
        conn_legacy = sqlite3.connect(path)
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
            conn = db.initialise(path)
            colonne = {
                row["name"] for row in conn.execute("PRAGMA table_info(mail_log)")
            }
            row = conn.execute("SELECT * FROM mail_log").fetchone()
            self.assertIn("senza_email", colonne)
            self.assertIn("registrata_il", colonne)
            self.assertEqual("2026-09-07T10:00:00", row["registrata_il"])
            self.assertEqual("Oggetto", row["oggetto"])
            self.assertFalse(db.automatic_email_delivery(conn))
            conn.close()

            conn = db.initialise(path)
            colonne_seconda = {
                row["name"] for row in conn.execute("PRAGMA table_info(mail_log)")
            }
            self.assertEqual(colonne, colonne_seconda)
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM mail_log").fetchone()[0])
            conn.close()
        finally:
            shutil.rmtree(folder, ignore_errors=True)


class ApiTests(unittest.TestCase):
    """Checks the API triggers and the log operations on a temporary archive."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.folder = Path(tempfile.mkdtemp(prefix="cicerone-email-api-test-"))
        original = db.initialise
        db.initialise = lambda path=db.DB_PATH: original(cls.folder / "piano.db")
        try:
            from app import main
        finally:
            db.initialise = original
        cls.main = main

    def setUp(self) -> None:
        self.conn = db.initialise(self.folder / f"test-{id(self)}.db")
        self.main.conn = self.conn
        self.fixture = make_fixture(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.folder, ignore_errors=True)

    def test_a_closed_plan_refuses_writes(self) -> None:
        """Hiding the buttons is a courtesy; refusing here is the guarantee."""
        import asyncio

        from fastapi import HTTPException

        from app import rules

        rules.close_plan(self.conn, self.fixture["piano"], "2026-09-09T10:00:00")
        session = self.main.SessionIn(
            piano_id=self.fixture["piano"], piano_modulo_id=self.fixture["modulo"],
            data="2026-09-20", ora_inizio="10:00", ora_fine="11:00",
            dettaglio="dopo la chiusura", note=None, tutor=[],
        )
        with self.assertRaises(HTTPException) as refused:
            asyncio.run(self.main.create_session(session))
        self.assertEqual(409, refused.exception.status_code)

        # and it accepts again once reopened
        rules.reopen_plan(self.conn, self.fixture["piano"])
        created = asyncio.run(self.main.create_session(session))
        self.assertIn("id", created)

    def test_the_state_carries_the_version(self) -> None:
        """Packages travel by USB: the version has to be readable on screen."""
        import asyncio

        from app import paths

        state = asyncio.run(self.main.state())
        self.assertEqual(paths.VERSION, state["version"])

    def test_create_move_and_cancel_endpoints_with_delivery_off(self) -> None:
        sender = MockSender()
        dati = self.main.SessionIn(
            piano_id=self.fixture["piano"], piano_modulo_id=self.fixture["modulo"],
            data="2026-09-08", ora_inizio="10:00", ora_fine="11:00",
            dettaglio="Nuovo coaching",
            tutor=[self.fixture["Bianchi"], self.fixture["Verdi"]],
        )
        with patch.object(delivery, "choose_channel", return_value=sender):
            creata = asyncio.run(self.main.create_session(dati))
            spostata = asyncio.run(self.main.update_session(
                creata["id"], self.main.SessionPatch(data="2026-09-09")
            ))
            annullata = asyncio.run(self.main.cancel_session(creata["id"]))
        self.assertEqual("invio_disattivato", creata["mail"]["esito"])
        self.assertEqual("invio_disattivato", spostata["mail"]["esito"])
        self.assertEqual("invio_disattivato", annullata["mail"]["esito"])
        self.assertEqual([], sender.calls)

    def test_api_retry_and_delete_leave_the_session_alone(self) -> None:
        message = messages.compose(self.conn, self.fixture["sessione"], "nuova")
        delivery.send(self.conn, message)
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        registro = asyncio.run(self.main.mail_log())
        self.assertIn("registrata_il", registro[0])
        retry_off = asyncio.run(self.main.retry_mail(voce["id"]))
        self.assertEqual("invio_disattivato", retry_off["esito"])

        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        sender = MockSender()
        with patch.object(delivery, "choose_channel", return_value=sender):
            retry_on = asyncio.run(self.main.retry_mail(voce["id"]))
        self.assertEqual("inviata", retry_on["esito"])
        self.assertEqual(1, len(sender.calls))

        asyncio.run(self.main.delete_mail(voce["id"]))
        self.assertIsNotNone(self.conn.execute(
            "SELECT id FROM sessione WHERE id = ?", (self.fixture["sessione"],)
        ).fetchone())
        self.assertIsNotNone(self.conn.execute(
            "SELECT id FROM piano WHERE id = ?", (self.fixture["piano"],)
        ).fetchone())
        self.assertIsNone(self.conn.execute(
            "SELECT id FROM mail_log WHERE id = ?", (voce["id"],)
        ).fetchone())

    def test_api_retry_and_delete_of_missing_entries404(self) -> None:
        with self.assertRaises(HTTPException) as retry_error:
            asyncio.run(self.main.retry_mail(999999))
        self.assertEqual(404, retry_error.exception.status_code)

        with self.assertRaises(HTTPException) as delete_error:
            asyncio.run(self.main.delete_mail(999999))
        self.assertEqual(404, delete_error.exception.status_code)

    def test_api_retry_of_a_sent_message_is_refused409(self) -> None:
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        sender = MockSender()
        with patch.object(delivery, "choose_channel", return_value=sender):
            delivery.send(self.conn, messages.compose(
                self.conn, self.fixture["sessione"], "nuova"
            ))
        voce = self.conn.execute("SELECT id FROM mail_log").fetchone()
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.main.retry_mail(voce["id"]))
        self.assertEqual(409, error.exception.status_code)

    def test_api_settings_persist(self) -> None:
        iniziale = asyncio.run(self.main.mail_settings())
        self.assertFalse(iniziale["invio_email_automatico"])
        attivata = asyncio.run(self.main.save_mail_settings(
            self.main.MailSettingIn(invio_email_automatico=True)
        ))
        self.assertTrue(attivata["invio_email_automatico"])
        persistita = asyncio.run(self.main.mail_settings())
        self.assertTrue(persistita["invio_email_automatico"])


if __name__ == "__main__":
    unittest.main()
