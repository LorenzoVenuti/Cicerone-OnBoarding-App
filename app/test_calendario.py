"""Test degli inviti per il calendario.

Il rischio vero non e' che l'invito non arrivi: e' che uno spostamento o una
disdetta finiscano sull'appuntamento sbagliato, cancellando dal calendario di
qualcuno un incontro che invece si tiene. Sono i test di questo file.
"""

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import calendario, db, mail


def campo(testo: str, nome: str) -> str:
    """Il valore di una riga dell'invito, riunendo le righe spezzate."""
    srotolato = testo.replace("\r\n ", "")
    for riga in srotolato.split("\r\n"):
        if riga.startswith(f"{nome}:"):
            return riga.split(":", 1)[1]
    return ""


class FormatoTests(unittest.TestCase):
    def _invito(self, **modifiche) -> str:
        parametri = {
            "uid": "abc@cicerone",
            "revisione": 0,
            "data": "2026-09-10",
            "ora_inizio": "09:30",
            "ora_fine": "11:30",
            "titolo": "Formazione: M05 - Qualita' e ambiente",
            "descrizione": "Modulo: M05\nTutor: Anna Bianchi",
            "organizzatore": "hr@esempio.test",
            "partecipanti": [{"nome": "Anna Bianchi", "email": "anna@esempio.test"}],
        }
        parametri.update(modifiche)
        return calendario.componi(**parametri)

    def test_e_un_invito_non_un_promemoria(self) -> None:
        testo = self._invito()
        self.assertIn("METHOD:REQUEST", testo)
        self.assertIn("BEGIN:VEVENT", testo)
        self.assertIn("ATTENDEE", testo)
        self.assertIn("mailto:anna@esempio.test", testo)

    def test_gli_orari_viaggiano_in_utc(self) -> None:
        """Senza fuso esplicito l'appuntamento cadrebbe nell'ora sbagliata."""
        testo = self._invito()
        atteso = (
            datetime(2026, 9, 10, 9, 30, tzinfo=ZoneInfo("Europe/Rome"))
            .astimezone(ZoneInfo("UTC"))
            .strftime("%Y%m%dT%H%M%SZ")
        )
        self.assertEqual(campo(testo, "DTSTART"), atteso)

    def test_i_caratteri_speciali_non_spezzano_l_invito(self) -> None:
        testo = self._invito(titolo="Riunione; con, virgole\ne a capo")
        self.assertIn("SUMMARY:Riunione\\; con\\, virgole\\ne a capo", testo)

    def test_le_righe_lunghe_vengono_spezzate(self) -> None:
        testo = self._invito(descrizione="x" * 300)
        for riga in testo.split("\r\n"):
            self.assertLessEqual(len(riga.encode("utf-8")), 75)

    def test_un_partecipante_senza_indirizzo_viene_saltato(self) -> None:
        testo = self._invito(
            partecipanti=[
                {"nome": "Senza Posta", "email": ""},
                {"nome": "Anna", "email": "anna@esempio.test"},
            ]
        )
        self.assertEqual(testo.count("ATTENDEE"), 1)

    def test_la_disdetta_riguarda_lo_stesso_appuntamento(self) -> None:
        disdetta = self._invito(revisione=3, annullato=True)
        self.assertIn("METHOD:CANCEL", disdetta)
        self.assertIn("STATUS:CANCELLED", disdetta)
        self.assertEqual(campo(disdetta, "UID"), "abc@cicerone")

    def test_ogni_appuntamento_ha_un_identificativo_diverso(self) -> None:
        self.assertNotEqual(calendario.nuovo_uid(), calendario.nuovo_uid())


class AppuntamentiDelPianoTests(unittest.TestCase):
    """Il caso che conta: piu' incontri fra le stesse persone."""

    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.inizializza(Path(self.cartella) / "prova.db")
        c = self.conn

        persona = c.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Anna', 'Bianchi', 'anna@esempio.test')"
        ).lastrowid
        self.tutor = c.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Marco', 'Verdi', 'marco@esempio.test')"
        ).lastrowid
        risorsa = c.execute(
            "INSERT INTO risorsa (persona_id, data_inizio) VALUES (?, '2026-01-07')",
            (persona,),
        ).lastrowid
        self.piano = c.execute(
            "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, '2026-01-01T09:00:00')",
            (risorsa,),
        ).lastrowid
        self.modulo = c.execute(
            """INSERT INTO piano_modulo (piano_id, codice, area, titolo, applicabile, ordine)
               VALUES (?, 'M05', 'Sistemi', 'Qualita e ambiente', 'SI', 1)""",
            (self.piano,),
        ).lastrowid
        c.commit()

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def sessione(self, data: str, inizio: str = "09:00", fine: str = "11:00") -> int:
        identificativo = self.conn.execute(
            """INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio,
                                     ora_fine, stato, creata_il, modificata_il)
               VALUES (?, ?, ?, ?, ?, 'Pianificata', '2026-01-01T09:00:00', '2026-01-01T09:00:00')""",
            (self.piano, self.modulo, data, inizio, fine),
        ).lastrowid
        self.conn.execute(
            "INSERT INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
            (identificativo, self.tutor),
        )
        self.conn.commit()
        return identificativo

    def test_due_incontri_fra_le_stesse_persone_restano_distinti(self) -> None:
        """Il punto delicato: spostare o disdire uno non deve toccare l'altro."""
        primo = self.sessione("2026-09-10")
        secondo = self.sessione("2026-09-17")

        uno = mail.componi(self.conn, primo, "nuova")
        due = mail.componi(self.conn, secondo, "nuova")

        self.assertNotEqual(
            campo(uno["calendario"], "UID"), campo(due["calendario"], "UID")
        )

        # si disdice solo il primo
        disdetta = mail.componi(self.conn, primo, "annullamento")
        self.assertIn("METHOD:CANCEL", disdetta["calendario"])
        self.assertEqual(
            campo(disdetta["calendario"], "UID"), campo(uno["calendario"], "UID")
        )
        self.assertNotEqual(
            campo(disdetta["calendario"], "UID"), campo(due["calendario"], "UID")
        )

    def test_spostare_aggiorna_lo_stesso_appuntamento(self) -> None:
        """Non si disdice e si ricrea: si sposta quello che c'e' gia'."""
        identificativo = self.sessione("2026-09-10")
        prima = mail.componi(self.conn, identificativo, "nuova")

        self.conn.execute(
            "UPDATE sessione SET data = '2026-09-24' WHERE id = ?", (identificativo,)
        )
        self.conn.commit()
        dopo = mail.componi(self.conn, identificativo, "spostamento")

        self.assertEqual(
            campo(prima["calendario"], "UID"), campo(dopo["calendario"], "UID")
        )
        self.assertIn("METHOD:REQUEST", dopo["calendario"])
        self.assertIn("20260924", campo(dopo["calendario"], "DTSTART"))

    def test_la_revisione_sale_a_ogni_avviso(self) -> None:
        """Senza revisione piu' alta i calendari scartano l'aggiornamento."""
        identificativo = self.sessione("2026-09-10")
        prima = mail.componi(self.conn, identificativo, "nuova")
        seconda = mail.componi(self.conn, identificativo, "spostamento")
        terza = mail.componi(self.conn, identificativo, "annullamento")

        self.assertEqual(campo(prima["calendario"], "SEQUENCE"), "0")
        self.assertEqual(campo(seconda["calendario"], "SEQUENCE"), "1")
        self.assertEqual(campo(terza["calendario"], "SEQUENCE"), "2")

    def test_l_identificativo_non_cambia_mai(self) -> None:
        identificativo = self.sessione("2026-09-10")
        mail.componi(self.conn, identificativo, "nuova")
        salvato = self.conn.execute(
            "SELECT uid_calendario FROM sessione WHERE id = ?", (identificativo,)
        ).fetchone()["uid_calendario"]

        mail.componi(self.conn, identificativo, "spostamento")
        di_nuovo = self.conn.execute(
            "SELECT uid_calendario FROM sessione WHERE id = ?", (identificativo,)
        ).fetchone()["uid_calendario"]
        self.assertEqual(salvato, di_nuovo)

    def test_invitati_sono_tutor_e_risorsa(self) -> None:
        identificativo = self.sessione("2026-09-10")
        invito = mail.componi(self.conn, identificativo, "nuova")["calendario"]
        self.assertIn("mailto:marco@esempio.test", invito)
        self.assertIn("mailto:anna@esempio.test", invito)

    def test_l_invito_viene_conservato_nel_registro(self) -> None:
        """Un 'riprova' deve rimandare lo stesso appuntamento, non uno nuovo."""
        identificativo = self.sessione("2026-09-10")
        messaggio = mail.componi(self.conn, identificativo, "nuova")
        mail.registra(self.conn, messaggio, "errore", "finto guasto")

        riga = self.conn.execute("SELECT * FROM mail_log").fetchone()
        ricostruito = mail.messaggio_da_log(riga)
        self.assertEqual(ricostruito["calendario"], messaggio["calendario"])


if __name__ == "__main__":
    unittest.main()
