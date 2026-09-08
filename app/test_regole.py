"""Test del cuore del programma: il piano calcolato, la chiusura automatica
e le sovrapposizioni.

Sono le regole che sostituiscono le formule del vecchio foglio Excel. I numeri
erano stati verificati uno a uno contro l'originale: questi test servono a non
perderli senza accorgersene.
"""

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import db, regole


class BaseConPiano(unittest.TestCase):
    """Un piano con due moduli e le persone che servono."""

    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.inizializza(Path(self.cartella) / "prova.db")
        c = self.conn

        self.risorsa_persona = c.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Anna', 'Bianchi', 'anna@esempio.test')"
        ).lastrowid
        self.tutor = c.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Marco', 'Verdi', 'marco@esempio.test')"
        ).lastrowid
        self.altro_tutor = c.execute(
            "INSERT INTO persona (nome, cognome) VALUES ('Sara', 'Neri')"
        ).lastrowid

        risorsa = c.execute(
            "INSERT INTO risorsa (persona_id, data_inizio) VALUES (?, '2026-01-07')",
            (self.risorsa_persona,),
        ).lastrowid
        self.piano = c.execute(
            "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, '2026-01-01T09:00:00')",
            (risorsa,),
        ).lastrowid

        self.modulo = c.execute(
            """INSERT INTO piano_modulo (piano_id, codice, area, titolo, applicabile, ordine)
               VALUES (?, 'M01', 'Generale', 'Presentazione', 'SI', 1)""",
            (self.piano,),
        ).lastrowid
        self.modulo_na = c.execute(
            """INSERT INTO piano_modulo (piano_id, codice, area, titolo, applicabile, ordine)
               VALUES (?, 'M02', 'IT', 'Gestionali', 'NO', 2)""",
            (self.piano,),
        ).lastrowid
        c.commit()

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def sessione(self, data, inizio="09:00", fine="11:00", stato="Pianificata",
                 modulo=None, tutor=(), piano=None, sostituisce=None) -> int:
        identificativo = self.conn.execute(
            """INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio,
                                     ora_fine, stato, sostituisce_id, creata_il, modificata_il)
               VALUES (?, ?, ?, ?, ?, ?, ?, '2026-01-01T09:00:00', '2026-01-01T09:00:00')""",
            (piano or self.piano, modulo if modulo is not None else self.modulo,
             data, inizio, fine, stato, sostituisce),
        ).lastrowid
        for persona in tutor:
            self.conn.execute(
                "INSERT INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
                (identificativo, persona),
            )
        self.conn.commit()
        return identificativo


class DurataTests(unittest.TestCase):
    def test_ore_intere_e_mezze(self) -> None:
        self.assertEqual(regole.durata_ore("09:00", "11:00"), 2.0)
        self.assertEqual(regole.durata_ore("09:30", "11:00"), 1.5)
        self.assertEqual(regole.durata_ore("09:00", "09:15"), 0.25)


class StatoModuloTests(unittest.TestCase):
    def test_non_applicabile_resta_na(self) -> None:
        self.assertEqual(regole.stato_modulo("NO", 5, 5), "N.A.")

    def test_senza_sessioni_e_da_pianificare(self) -> None:
        self.assertEqual(regole.stato_modulo("SI", 0, 0), "Da pianificare")

    def test_tutte_svolte_e_completata(self) -> None:
        self.assertEqual(regole.stato_modulo("SI", 2, 2), "Completata")

    def test_alcune_svolte_e_in_corso(self) -> None:
        self.assertEqual(regole.stato_modulo("SI", 3, 1), "In corso")

    def test_pianificate_ma_nessuna_svolta(self) -> None:
        self.assertEqual(regole.stato_modulo("SI", 2, 0), "Pianificata")


class RiepilogoModuliTests(BaseConPiano):
    """Il foglio 'Piano ISO' calcolato dalle sole sessioni."""

    def test_conta_ore_e_date_solo_delle_sessioni_valide(self) -> None:
        self.sessione("2026-01-10", "09:00", "11:00", "Svolta")
        self.sessione("2026-01-20", "09:00", "12:00", "Svolta")
        self.sessione("2026-01-30", "09:00", "11:00", "Pianificata")
        # queste non devono contare
        self.sessione("2026-01-05", "09:00", "18:00", "Annullata")
        self.sessione("2026-02-28", "09:00", "18:00", "Rinviata")

        riga = next(m for m in regole.riepilogo_moduli(self.conn, self.piano)
                    if m["id"] == self.modulo)

        self.assertEqual(riga["sessioni_pianificate"], 3)
        self.assertEqual(riga["sessioni_svolte"], 2)
        self.assertEqual(riga["ore_svolte"], 5.0)
        self.assertEqual(riga["dal"], "2026-01-10")
        self.assertEqual(riga["al"], "2026-01-30")
        self.assertEqual(riga["stato"], "In corso")

    def test_un_modulo_senza_sessioni_e_da_pianificare(self) -> None:
        riga = next(m for m in regole.riepilogo_moduli(self.conn, self.piano)
                    if m["id"] == self.modulo)
        self.assertEqual(riga["stato"], "Da pianificare")
        self.assertIsNone(riga["dal"])
        self.assertEqual(riga["ore_svolte"], 0)

    def test_il_modulo_non_applicabile_resta_na_anche_con_sessioni(self) -> None:
        self.sessione("2026-01-10", stato="Svolta", modulo=self.modulo_na)
        riga = next(m for m in regole.riepilogo_moduli(self.conn, self.piano)
                    if m["id"] == self.modulo_na)
        self.assertEqual(riga["stato"], "N.A.")

    def test_il_piano_e_calcolato_non_memorizzato(self) -> None:
        """Aggiungendo una sessione il riepilogo cambia da solo."""
        prima = next(m for m in regole.riepilogo_moduli(self.conn, self.piano)
                     if m["id"] == self.modulo)
        self.sessione("2026-01-10", "09:00", "13:00", "Svolta")
        dopo = next(m for m in regole.riepilogo_moduli(self.conn, self.piano)
                    if m["id"] == self.modulo)

        self.assertEqual(prima["ore_svolte"], 0)
        self.assertEqual(dopo["ore_svolte"], 4.0)


class ChiusuraAutomaticaTests(BaseConPiano):
    def test_chiude_le_passate_e_le_segna_automatiche(self) -> None:
        vecchia = self.sessione("2026-01-10")
        regole.chiudi_sessioni_passate(self.conn, datetime(2026, 1, 15, 9, 0))

        riga = self.conn.execute(
            "SELECT * FROM sessione WHERE id = ?", (vecchia,)
        ).fetchone()
        self.assertEqual(riga["stato"], "Svolta")
        self.assertEqual(riga["esito_verifica"], "OK")
        self.assertEqual(riga["chiusa_automaticamente"], 1)

    def test_la_giornata_di_oggi_si_chiude_solo_dopo_le_18(self) -> None:
        self.sessione("2026-01-15")
        mattina = regole.sessioni_da_chiudere(self.conn, datetime(2026, 1, 15, 9, 0))
        self.assertEqual(mattina, [])

        sera = regole.sessioni_da_chiudere(self.conn, datetime(2026, 1, 15, 18, 30))
        self.assertEqual(len(sera), 1)

    def test_non_tocca_quelle_future(self) -> None:
        self.sessione("2026-03-01")
        self.assertEqual(
            regole.sessioni_da_chiudere(self.conn, datetime(2026, 1, 15, 9, 0)), []
        )

    def test_non_tocca_annullate_e_svolte(self) -> None:
        self.sessione("2026-01-10", stato="Annullata")
        self.sessione("2026-01-11", stato="Svolta")
        self.assertEqual(
            regole.sessioni_da_chiudere(self.conn, datetime(2026, 1, 15, 9, 0)), []
        )

    def test_una_sessione_riprogrammata_non_viene_chiusa(self) -> None:
        """Se qualcuno l'ha gia' spostata a mano, non e' una dimenticanza."""
        vecchia = self.sessione("2026-01-10")
        self.sessione("2026-02-10", sostituisce=vecchia)
        self.assertEqual(
            regole.sessioni_da_chiudere(self.conn, datetime(2026, 1, 15, 9, 0)), []
        )

    def test_e_idempotente(self) -> None:
        """Due avvii di fila non devono cambiare niente la seconda volta."""
        self.sessione("2026-01-10")
        adesso = datetime(2026, 1, 15, 9, 0)
        self.assertEqual(len(regole.chiudi_sessioni_passate(self.conn, adesso)), 1)
        self.assertEqual(regole.chiudi_sessioni_passate(self.conn, adesso), [])

    def test_non_sovrascrive_un_esito_gia_scritto_da_una_persona(self) -> None:
        vecchia = self.sessione("2026-01-10")
        self.conn.execute(
            "UPDATE sessione SET esito_verifica = 'Da ripetere' WHERE id = ?", (vecchia,)
        )
        self.conn.commit()
        regole.chiudi_sessioni_passate(self.conn, datetime(2026, 1, 15, 9, 0))
        riga = self.conn.execute(
            "SELECT esito_verifica FROM sessione WHERE id = ?", (vecchia,)
        ).fetchone()
        self.assertEqual(riga["esito_verifica"], "Da ripetere")


class SovrapposizioniTests(BaseConPiano):
    def test_la_risorsa_non_puo_essere_in_due_posti(self) -> None:
        self.sessione("2026-02-02", "09:00", "11:00")
        conflitti = regole.sovrapposizioni(
            self.conn, self.piano, "2026-02-02", "10:00", "12:00"
        )
        self.assertEqual(len(conflitti), 1)
        self.assertEqual(conflitti[0]["motivo"], "risorsa")

    def test_orari_che_si_toccano_non_sono_sovrapposti(self) -> None:
        self.sessione("2026-02-02", "09:00", "11:00")
        self.assertEqual(
            regole.sovrapposizioni(self.conn, self.piano, "2026-02-02", "11:00", "12:00"),
            [],
        )

    def test_annullate_e_rinviate_non_danno_conflitto(self) -> None:
        self.sessione("2026-02-02", "09:00", "11:00", stato="Annullata")
        self.sessione("2026-02-02", "09:00", "11:00", stato="Rinviata")
        self.assertEqual(
            regole.sovrapposizioni(self.conn, self.piano, "2026-02-02", "09:30", "10:30"),
            [],
        )

    def test_un_tutor_impegnato_su_un_altro_piano(self) -> None:
        altra_persona = self.conn.execute(
            "INSERT INTO persona (nome, cognome) VALUES ('Luca', 'Gialli')"
        ).lastrowid
        altra_risorsa = self.conn.execute(
            "INSERT INTO risorsa (persona_id, data_inizio) VALUES (?, '2026-01-07')",
            (altra_persona,),
        ).lastrowid
        altro_piano = self.conn.execute(
            "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, '2026-01-01T09:00:00')",
            (altra_risorsa,),
        ).lastrowid
        self.conn.commit()
        self.sessione("2026-02-02", "09:00", "11:00", modulo=None,
                      tutor=[self.tutor], piano=altro_piano)

        conflitti = regole.sovrapposizioni(
            self.conn, self.piano, "2026-02-02", "10:00", "12:00", tutor=[self.tutor]
        )
        self.assertEqual(len(conflitti), 1)
        self.assertEqual(conflitti[0]["motivo"], "tutor")

    def test_si_puo_escludere_la_sessione_che_si_sta_modificando(self) -> None:
        identificativo = self.sessione("2026-02-02", "09:00", "11:00")
        self.assertEqual(
            regole.sovrapposizioni(
                self.conn, self.piano, "2026-02-02", "09:00", "11:00",
                escludi_sessione=identificativo,
            ),
            [],
        )


class ColoriAreeTests(BaseConPiano):
    def test_ogni_area_riceve_un_colore_e_non_cambia_piu(self) -> None:
        regole.assicura_colori_aree(self.conn)
        colori = {r["nome"]: r["colore"]
                  for r in self.conn.execute("SELECT nome, colore FROM area")}
        self.assertIn("Generale", colori)
        self.assertIn("IT", colori)

        regole.assicura_colori_aree(self.conn)   # seconda volta: stabile
        di_nuovo = {r["nome"]: r["colore"]
                    for r in self.conn.execute("SELECT nome, colore FROM area")}
        self.assertEqual(colori, di_nuovo)


if __name__ == "__main__":
    unittest.main()
