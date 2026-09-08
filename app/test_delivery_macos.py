"""Tests for the macOS delivery channels and for choosing a channel.

None of these tests really talks to a mail program: `osascript` is replaced by
a stand-in, or the suite would send real mail.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, delivery


def _esito(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


MESSAGGIO = {
    "tipo": "nuova",
    "sessione_id": 1,
    "oggetto": 'Formazione: "Qualita" e ambiente',
    "corpo": "Buongiorno,\nl'incontro e' confermato.\n-- Ufficio HR",
    "destinatari": ["mario@esempio.test", "lucia@esempio.test"],
    "senza_email": [],
}


class AvailabilityTests(unittest.TestCase):
    def test_off_macos_no_applescript_channel(self) -> None:
        with patch("app.delivery.platform.system", return_value="Windows"):
            self.assertFalse(delivery.OutlookMac().available())
            self.assertFalse(delivery.AppleMail().available())

    def test_on_macos_the_program_must_be_installed(self) -> None:
        with patch("app.delivery.platform.system", return_value="Darwin"):
            with patch.object(delivery.OutlookMac, "PATHS", (Path("/"),)):
                self.assertTrue(delivery.OutlookMac().available())
            with patch.object(delivery.OutlookMac, "PATHS", (Path("/non/esiste"),)):
                self.assertFalse(delivery.OutlookMac().available())


class SendTests(unittest.TestCase):
    """The delicate part: data must never end up inside the script source."""

    def test_data_is_passed_as_arguments_not_as_code(self) -> None:
        with patch("app.delivery.subprocess.run", return_value=_esito()) as run:
            delivery.AppleMail(sender="hr@esempio.test").send(MESSAGGIO)

        comando = run.call_args.args[0]
        self.assertEqual(comando[0], "osascript")
        self.assertEqual(comando[1], "-")            # script da stdin
        self.assertEqual(comando[2], MESSAGGIO["oggetto"])
        self.assertEqual(comando[3], MESSAGGIO["corpo"])
        self.assertEqual(comando[4], "hr@esempio.test")
        self.assertEqual(comando[5], "")             # nessun invito allegato
        self.assertEqual(comando[6:], MESSAGGIO["destinatari"])

        script = run.call_args.kwargs["input"]
        self.assertNotIn("Qualita", script)
        self.assertNotIn("esempio.test", script)

    def test_with_no_sender_chosen_an_empty_string_is_passed(self) -> None:
        with patch("app.delivery.subprocess.run", return_value=_esito()) as run:
            delivery.AppleMail().send(MESSAGGIO)
        self.assertEqual(run.call_args.args[0][4], "")

    def test_the_invitation_is_written_to_a_file_and_attached(self) -> None:
        """Mail programs attach from disk, not from memory."""
        con_invito = {**MESSAGGIO, "calendario": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"}
        visto = {}

        def registra(comando, **kwargs):
            percorso = Path(comando[5])
            visto["nome"] = percorso.name
            visto["contenuto"] = percorso.read_text(encoding="utf-8")
            return _esito()

        with patch("app.delivery.subprocess.run", side_effect=registra):
            delivery.AppleMail().send(con_invito)

        self.assertEqual(visto["nome"], "invito.ics")
        self.assertIn("BEGIN:VCALENDAR", visto["contenuto"])

    def test_the_temporary_file_is_cleaned_up(self) -> None:
        paths = []
        with delivery.invitation_file("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n") as percorso:
            paths.append(Path(percorso))
            self.assertTrue(paths[0].exists())
        self.assertFalse(paths[0].exists())

    def test_each_program_uses_its_own_text_field(self) -> None:
        """Mail wants `content`, Outlook `plain text content`: with the wrong one
        the text would be treated as HTML and lose its line breaks."""
        with patch("app.delivery.subprocess.run", return_value=_esito()) as run:
            delivery.AppleMail().send(MESSAGGIO)
            self.assertIn("content:theBody", run.call_args.kwargs["input"])
            delivery.OutlookMac().send(MESSAGGIO)
            self.assertIn("plain text content:theBody", run.call_args.kwargs["input"])

    def test_scripts_verify_the_message_left_the_outbox(self) -> None:
        """Without this check a queued message would count as delivered."""
        for canale in (delivery.AppleMail(), delivery.OutlookMac()):
            with patch("app.delivery.subprocess.run", return_value=_esito()) as run:
                canale.send(MESSAGGIO)
            script = run.call_args.kwargs["input"]
            self.assertIn("STUCK_IN_OUTBOX", script)
            self.assertIn("NO_ACCOUNT", script)

    def test_no_recipients_means_no_osascript_call(self) -> None:
        with patch("app.delivery.subprocess.run") as run:
            with self.assertRaises(delivery.DeliveryError):
                delivery.AppleMail().send({**MESSAGGIO, "destinatari": []})
        run.assert_not_called()


class ErrorTests(unittest.TestCase):
    def test_no_account_becomes_a_readable_message(self) -> None:
        with patch("app.delivery.subprocess.run",
                   return_value=_esito(1, stderr='error "NO_ACCOUNT" number 1001')):
            with self.assertRaises(delivery.DeliveryError) as contesto:
                delivery.OutlookMac().send(MESSAGGIO)
        self.assertIn("nessun account", str(contesto.exception))

    def test_a_message_stuck_in_the_outbox_is_not_a_success(self) -> None:
        with patch("app.delivery.subprocess.run",
                   return_value=_esito(1, stderr='error "STUCK_IN_OUTBOX" number 1002')):
            with self.assertRaises(delivery.DeliveryError) as contesto:
                delivery.AppleMail().send(MESSAGGIO)
        self.assertIn("posta in uscita", str(contesto.exception))

    def test_denied_permission_explains_where_to_grant_it(self) -> None:
        errore = "execution error: Not authorized to send Apple events (-1743)"
        with patch("app.delivery.subprocess.run", return_value=_esito(1, stderr=errore)):
            with self.assertRaises(delivery.DeliveryError) as contesto:
                delivery.AppleMail().send(MESSAGGIO)
        self.assertIn("Privacy & Security", str(contesto.exception))

    def test_a_timeout_becomes_a_delivery_error(self) -> None:
        with patch("app.delivery.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=60)):
            with self.assertRaises(delivery.DeliveryError):
                delivery.AppleMail().send(MESSAGGIO)


class AccountTests(unittest.TestCase):
    def test_reads_the_addresses_one_line_at_a_time(self) -> None:
        uscita = "hr@esempio.test\n  mario@esempio.test  \n\n"
        with patch("app.delivery.platform.system", return_value="Darwin"), \
             patch.object(delivery.AppleMail, "PATHS", (Path("/"),)), \
             patch("app.delivery.subprocess.run", return_value=_esito(stdout=uscita)):
            self.assertEqual(
                delivery.AppleMail().accounts(),
                ["hr@esempio.test", "mario@esempio.test"],
            )

    def test_no_accounts_when_the_program_does_not_answer(self) -> None:
        with patch("app.delivery.platform.system", return_value="Darwin"), \
             patch.object(delivery.AppleMail, "PATHS", (Path("/"),)), \
             patch("app.delivery.subprocess.run", return_value=_esito(1, stderr="boom")):
            self.assertEqual(delivery.AppleMail().accounts(), [])


class ChannelChoiceTests(unittest.TestCase):
    """The channel is not guessed: it is configured once and remembered."""

    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.initialise(Path(self.cartella) / "prova.db")

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def test_uses_the_configured_channel(self) -> None:
        db.save_setting(self.conn, db.KEY_MAIL_CHANNEL, "outlook_mac")
        db.save_setting(self.conn, db.KEY_MAIL_SENDER, "hr@esempio.test")
        canale = delivery.choose_channel(self.conn)
        self.assertEqual(canale.name, "outlook_mac")
        self.assertEqual(canale.sender, "hr@esempio.test")

    def test_without_setup_the_app_still_starts(self) -> None:
        """Until it is configured the app must still start."""
        canale = delivery.choose_channel(self.conn)
        self.assertIn(canale.name, {c.name for c in delivery.CHANNELS})

    def test_an_unknown_stored_channel_does_not_break_startup(self) -> None:
        db.save_setting(self.conn, db.KEY_MAIL_CHANNEL, "piccione_viaggiatore")
        self.assertIsNotNone(delivery.choose_channel(self.conn))

    def test_channel_by_name(self) -> None:
        self.assertIsNone(delivery.channel_by_name("inesistente"))
        self.assertEqual(delivery.channel_by_name("file").name, "file")


if __name__ == "__main__":
    unittest.main()
