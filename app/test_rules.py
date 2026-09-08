"""Tests for the heart of the program: the computed plan, automatic closing
and clash detection.

These are the rules that replace the formulas of the old spreadsheet. The
numbers had been checked one by one against the original: these tests exist so
they cannot be lost without anybody noticing.
"""

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import db, rules


class PlanFixture(unittest.TestCase):
    """A plan with two modules and the people it needs."""

    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.initialise(Path(self.cartella) / "prova.db")
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


class DurationTests(unittest.TestCase):
    def test_whole_and_half_hours(self) -> None:
        self.assertEqual(rules.duration_hours("09:00", "11:00"), 2.0)
        self.assertEqual(rules.duration_hours("09:30", "11:00"), 1.5)
        self.assertEqual(rules.duration_hours("09:00", "09:15"), 0.25)


class ModuleStateTests(unittest.TestCase):
    def test_not_applicable_stays_na(self) -> None:
        self.assertEqual(rules.module_state("NO", 5, 5), "N.A.")

    def test_no_sessions_means_still_to_plan(self) -> None:
        self.assertEqual(rules.module_state("SI", 0, 0), "Da pianificare")

    def test_all_done_means_completed(self) -> None:
        self.assertEqual(rules.module_state("SI", 2, 2), "Completata")

    def test_some_done_means_in_progress(self) -> None:
        self.assertEqual(rules.module_state("SI", 3, 1), "In corso")

    def test_planned_but_none_done(self) -> None:
        self.assertEqual(rules.module_state("SI", 2, 0), "Pianificata")


class ModuleSummaryTests(PlanFixture):
    """The training plan, computed from the sessions alone."""

    def test_counts_hours_and_dates_of_valid_sessions_only(self) -> None:
        self.sessione("2026-01-10", "09:00", "11:00", "Svolta")
        self.sessione("2026-01-20", "09:00", "12:00", "Svolta")
        self.sessione("2026-01-30", "09:00", "11:00", "Pianificata")
        # these must not count
        self.sessione("2026-01-05", "09:00", "18:00", "Annullata")
        self.sessione("2026-02-28", "09:00", "18:00", "Rinviata")

        riga = next(m for m in rules.module_summary(self.conn, self.piano)
                    if m["id"] == self.modulo)

        self.assertEqual(riga["sessioni_pianificate"], 3)
        self.assertEqual(riga["sessioni_svolte"], 2)
        self.assertEqual(riga["ore_svolte"], 5.0)
        self.assertEqual(riga["dal"], "2026-01-10")
        self.assertEqual(riga["al"], "2026-01-30")
        self.assertEqual(riga["stato"], "In corso")

    def test_a_module_with_no_sessions_is_still_to_plan(self) -> None:
        riga = next(m for m in rules.module_summary(self.conn, self.piano)
                    if m["id"] == self.modulo)
        self.assertEqual(riga["stato"], "Da pianificare")
        self.assertIsNone(riga["dal"])
        self.assertEqual(riga["ore_svolte"], 0)

    def test_a_non_applicable_module_stays_na(self) -> None:
        self.sessione("2026-01-10", stato="Svolta", modulo=self.modulo_na)
        riga = next(m for m in rules.module_summary(self.conn, self.piano)
                    if m["id"] == self.modulo_na)
        self.assertEqual(riga["stato"], "N.A.")

    def test_the_plan_is_calculated_not_stored(self) -> None:
        """Adding a session changes the summary on its own."""
        prima = next(m for m in rules.module_summary(self.conn, self.piano)
                     if m["id"] == self.modulo)
        self.sessione("2026-01-10", "09:00", "13:00", "Svolta")
        dopo = next(m for m in rules.module_summary(self.conn, self.piano)
                    if m["id"] == self.modulo)

        self.assertEqual(prima["ore_svolte"], 0)
        self.assertEqual(dopo["ore_svolte"], 4.0)


class AutomaticClosingTests(PlanFixture):
    def test_closes_past_sessions_and_flags_them_automatic(self) -> None:
        vecchia = self.sessione("2026-01-10")
        rules.close_past_sessions(self.conn, datetime(2026, 1, 15, 9, 0))

        riga = self.conn.execute(
            "SELECT * FROM sessione WHERE id = ?", (vecchia,)
        ).fetchone()
        self.assertEqual(riga["stato"], "Svolta")
        self.assertEqual(riga["esito_verifica"], "OK")
        self.assertEqual(riga["chiusa_automaticamente"], 1)

    def test_today_closes_only_after_the_cutoff_hour18(self) -> None:
        self.sessione("2026-01-15")
        mattina = rules.sessions_to_close(self.conn, datetime(2026, 1, 15, 9, 0))
        self.assertEqual(mattina, [])

        sera = rules.sessions_to_close(self.conn, datetime(2026, 1, 15, 18, 30))
        self.assertEqual(len(sera), 1)

    def test_leaves_future_sessions_alone(self) -> None:
        self.sessione("2026-03-01")
        self.assertEqual(
            rules.sessions_to_close(self.conn, datetime(2026, 1, 15, 9, 0)), []
        )

    def test_leaves_cancelled_and_done_alone(self) -> None:
        self.sessione("2026-01-10", stato="Annullata")
        self.sessione("2026-01-11", stato="Svolta")
        self.assertEqual(
            rules.sessions_to_close(self.conn, datetime(2026, 1, 15, 9, 0)), []
        )

    def test_a_rescheduled_session_is_not_closed(self) -> None:
        """If somebody already moved it by hand, it is not an oversight."""
        vecchia = self.sessione("2026-01-10")
        self.sessione("2026-02-10", sostituisce=vecchia)
        self.assertEqual(
            rules.sessions_to_close(self.conn, datetime(2026, 1, 15, 9, 0)), []
        )

    def test_is_idempotent(self) -> None:
        """Two runs in a row must change nothing the second time."""
        self.sessione("2026-01-10")
        adesso = datetime(2026, 1, 15, 9, 0)
        self.assertEqual(len(rules.close_past_sessions(self.conn, adesso)), 1)
        self.assertEqual(rules.close_past_sessions(self.conn, adesso), [])

    def test_does_not_overwrite_an_outcome_set_by_a_person(self) -> None:
        vecchia = self.sessione("2026-01-10")
        self.conn.execute(
            "UPDATE sessione SET esito_verifica = 'Da ripetere' WHERE id = ?", (vecchia,)
        )
        self.conn.commit()
        rules.close_past_sessions(self.conn, datetime(2026, 1, 15, 9, 0))
        riga = self.conn.execute(
            "SELECT esito_verifica FROM sessione WHERE id = ?", (vecchia,)
        ).fetchone()
        self.assertEqual(riga["esito_verifica"], "Da ripetere")


class OverlapTests(PlanFixture):
    def test_the_trainee_cannot_be_in_two_places(self) -> None:
        self.sessione("2026-02-02", "09:00", "11:00")
        conflitti = rules.overlaps(
            self.conn, self.piano, "2026-02-02", "10:00", "12:00"
        )
        self.assertEqual(len(conflitti), 1)
        self.assertEqual(conflitti[0]["motivo"], "risorsa")

    def test_touching_times_do_not_overlap(self) -> None:
        self.sessione("2026-02-02", "09:00", "11:00")
        self.assertEqual(
            rules.overlaps(self.conn, self.piano, "2026-02-02", "11:00", "12:00"),
            [],
        )

    def test_cancelled_and_postponed_do_not_clash(self) -> None:
        self.sessione("2026-02-02", "09:00", "11:00", stato="Annullata")
        self.sessione("2026-02-02", "09:00", "11:00", stato="Rinviata")
        self.assertEqual(
            rules.overlaps(self.conn, self.piano, "2026-02-02", "09:30", "10:30"),
            [],
        )

    def test_a_tutor_busy_on_another_plan(self) -> None:
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

        conflitti = rules.overlaps(
            self.conn, self.piano, "2026-02-02", "10:00", "12:00", tutors=[self.tutor]
        )
        self.assertEqual(len(conflitti), 1)
        self.assertEqual(conflitti[0]["motivo"], "tutor")

    def test_the_session_being_edited_can_be_excluded(self) -> None:
        identificativo = self.sessione("2026-02-02", "09:00", "11:00")
        self.assertEqual(
            rules.overlaps(
                self.conn, self.piano, "2026-02-02", "09:00", "11:00",
                ignore_session=identificativo,
            ),
            [],
        )


class AreaColourTests(PlanFixture):
    def test_every_area_gets_a_colour_and_keeps_it(self) -> None:
        rules.ensure_area_colours(self.conn)
        colori = {r["nome"]: r["colore"]
                  for r in self.conn.execute("SELECT nome, colore FROM area")}
        self.assertIn("Generale", colori)
        self.assertIn("IT", colori)

        rules.ensure_area_colours(self.conn)   # seconda volta: stabile
        di_nuovo = {r["nome"]: r["colore"]
                    for r in self.conn.execute("SELECT nome, colore FROM area")}
        self.assertEqual(colori, di_nuovo)


if __name__ == "__main__":
    unittest.main()
