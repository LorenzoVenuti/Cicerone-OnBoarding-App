"""Test dei canali di invio su macOS e della scelta del canale.

Nessuno di questi test parla davvero con un programma di posta: `osascript` e'
sostituito da un finto, altrimenti la suite manderebbe posta vera.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, invio


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


class DisponibilitaTests(unittest.TestCase):
    def test_fuori_da_mac_nessun_canale_applescript(self) -> None:
        with patch("app.invio.platform.system", return_value="Windows"):
            self.assertFalse(invio.InvioOutlookMac().disponibile())
            self.assertFalse(invio.InvioMailMac().disponibile())

    def test_su_mac_serve_il_programma_installato(self) -> None:
        with patch("app.invio.platform.system", return_value="Darwin"):
            with patch.object(invio.InvioOutlookMac, "PERCORSI", (Path("/"),)):
                self.assertTrue(invio.InvioOutlookMac().disponibile())
            with patch.object(invio.InvioOutlookMac, "PERCORSI", (Path("/non/esiste"),)):
                self.assertFalse(invio.InvioOutlookMac().disponibile())


class InvioTests(unittest.TestCase):
    """Il punto delicato: i dati non devono mai finire nel sorgente."""

    def test_i_dati_passano_come_argomenti_non_come_codice(self) -> None:
        with patch("app.invio.subprocess.run", return_value=_esito()) as run:
            invio.InvioMailMac(mittente="hr@esempio.test").invia(MESSAGGIO)

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

    def test_senza_mittente_scelto_si_passa_stringa_vuota(self) -> None:
        with patch("app.invio.subprocess.run", return_value=_esito()) as run:
            invio.InvioMailMac().invia(MESSAGGIO)
        self.assertEqual(run.call_args.args[0][4], "")

    def test_l_invito_viene_scritto_su_file_e_allegato(self) -> None:
        """I programmi di posta allegano da disco, non da memoria."""
        con_invito = {**MESSAGGIO, "calendario": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"}
        visto = {}

        def registra(comando, **kwargs):
            percorso = Path(comando[5])
            visto["nome"] = percorso.name
            visto["contenuto"] = percorso.read_text(encoding="utf-8")
            return _esito()

        with patch("app.invio.subprocess.run", side_effect=registra):
            invio.InvioMailMac().invia(con_invito)

        self.assertEqual(visto["nome"], "invito.ics")
        self.assertIn("BEGIN:VCALENDAR", visto["contenuto"])

    def test_il_file_temporaneo_viene_ripulito(self) -> None:
        percorsi = []
        with invio.file_invito("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n") as percorso:
            percorsi.append(Path(percorso))
            self.assertTrue(percorsi[0].exists())
        self.assertFalse(percorsi[0].exists())

    def test_ogni_programma_usa_il_suo_campo_di_testo(self) -> None:
        """Mail vuole `content`, Outlook `plain text content`: con l'altro il
        testo verrebbe trattato come HTML e perderebbe gli a capo."""
        with patch("app.invio.subprocess.run", return_value=_esito()) as run:
            invio.InvioMailMac().invia(MESSAGGIO)
            self.assertIn("content:corpo", run.call_args.kwargs["input"])
            invio.InvioOutlookMac().invia(MESSAGGIO)
            self.assertIn("plain text content:corpo", run.call_args.kwargs["input"])

    def test_gli_script_verificano_che_il_messaggio_esca_dalla_coda(self) -> None:
        """Senza questo controllo un messaggio accodato risulterebbe inviato."""
        for canale in (invio.InvioMailMac(), invio.InvioOutlookMac()):
            with patch("app.invio.subprocess.run", return_value=_esito()) as run:
                canale.invia(MESSAGGIO)
            script = run.call_args.kwargs["input"]
            self.assertIn("RESTA_IN_CODA", script)
            self.assertIn("NESSUN_ACCOUNT", script)

    def test_senza_destinatari_non_chiama_osascript(self) -> None:
        with patch("app.invio.subprocess.run") as run:
            with self.assertRaises(invio.ErroreInvio):
                invio.InvioMailMac().invia({**MESSAGGIO, "destinatari": []})
        run.assert_not_called()


class ErroriTests(unittest.TestCase):
    def test_nessun_account_diventa_messaggio_comprensibile(self) -> None:
        with patch("app.invio.subprocess.run",
                   return_value=_esito(1, stderr='error "NESSUN_ACCOUNT" number 1001')):
            with self.assertRaises(invio.ErroreInvio) as contesto:
                invio.InvioOutlookMac().invia(MESSAGGIO)
        self.assertIn("nessun account", str(contesto.exception))

    def test_messaggio_rimasto_in_coda_non_e_un_successo(self) -> None:
        with patch("app.invio.subprocess.run",
                   return_value=_esito(1, stderr='error "RESTA_IN_CODA" number 1002')):
            with self.assertRaises(invio.ErroreInvio) as contesto:
                invio.InvioMailMac().invia(MESSAGGIO)
        self.assertIn("posta in uscita", str(contesto.exception))

    def test_permesso_negato_spiega_dove_concederlo(self) -> None:
        errore = "execution error: Not authorized to send Apple events (-1743)"
        with patch("app.invio.subprocess.run", return_value=_esito(1, stderr=errore)):
            with self.assertRaises(invio.ErroreInvio) as contesto:
                invio.InvioMailMac().invia(MESSAGGIO)
        self.assertIn("Privacy & Security", str(contesto.exception))

    def test_timeout_diventa_errore_di_invio(self) -> None:
        with patch("app.invio.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=60)):
            with self.assertRaises(invio.ErroreInvio):
                invio.InvioMailMac().invia(MESSAGGIO)


class AccountTests(unittest.TestCase):
    def test_legge_gli_indirizzi_una_riga_per_volta(self) -> None:
        uscita = "hr@esempio.test\n  mario@esempio.test  \n\n"
        with patch("app.invio.platform.system", return_value="Darwin"), \
             patch.object(invio.InvioMailMac, "PERCORSI", (Path("/"),)), \
             patch("app.invio.subprocess.run", return_value=_esito(stdout=uscita)):
            self.assertEqual(
                invio.InvioMailMac().account(),
                ["hr@esempio.test", "mario@esempio.test"],
            )

    def test_se_il_programma_non_risponde_niente_account(self) -> None:
        with patch("app.invio.platform.system", return_value="Darwin"), \
             patch.object(invio.InvioMailMac, "PERCORSI", (Path("/"),)), \
             patch("app.invio.subprocess.run", return_value=_esito(1, stderr="boom")):
            self.assertEqual(invio.InvioMailMac().account(), [])


class SceltaCanaleTests(unittest.TestCase):
    """Il canale non si indovina: si configura una volta e si ricorda."""

    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.inizializza(Path(self.cartella) / "prova.db")

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def test_usa_il_canale_configurato(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_CANALE_MAIL, "outlook_mac")
        db.salva_impostazione(self.conn, db.CHIAVE_MITTENTE_MAIL, "hr@esempio.test")
        canale = invio.scegli_canale(self.conn)
        self.assertEqual(canale.nome, "outlook_mac")
        self.assertEqual(canale.mittente, "hr@esempio.test")

    def test_senza_configurazione_non_si_blocca(self) -> None:
        """Finche' non e' configurato l'app deve comunque partire."""
        canale = invio.scegli_canale(self.conn)
        self.assertIn(canale.nome, {c.nome for c in invio.CANALI})

    def test_un_canale_salvato_ma_ignoto_non_rompe_l_avvio(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_CANALE_MAIL, "piccione_viaggiatore")
        self.assertIsNotNone(invio.scegli_canale(self.conn))

    def test_canale_per_nome(self) -> None:
        self.assertIsNone(invio.canale_per_nome("inesistente"))
        self.assertEqual(invio.canale_per_nome("file").nome, "file")


if __name__ == "__main__":
    unittest.main()
