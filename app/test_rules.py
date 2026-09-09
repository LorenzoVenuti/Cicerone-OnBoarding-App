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

        rules.ensure_area_colours(self.conn)   # a second time: stable
        again = {r["nome"]: r["colore"]
                 for r in self.conn.execute("SELECT nome, colore FROM area")}
        self.assertEqual(colori, again)


class ModuleReachesOpenPlansTests(PlanFixture):
    """Filling the catalogue after creating a trainee must not leave them empty.

    Starting from an empty archive, creating the person first and the modules
    afterwards is the natural order, and it used to produce a plan with nothing
    in it: the plan copies the catalogue as it was the day it was created.
    """

    def _catalogue(self, code: str = "M09", title: str = "Ciclo passivo") -> None:
        self.conn.execute(
            """INSERT INTO modulo_catalogo (codice, area, titolo, modalita_default, ordine)
               VALUES (?, 'Acquisti', ?, 'Spiegazione', 9)""",
            (code, title),
        )
        self.conn.commit()

    def test_a_module_catalogued_later_reaches_an_open_plan(self) -> None:
        self._catalogue()
        self.assertEqual(1, rules.add_module_to_open_plans(self.conn, "M09"))

        codes = [r["codice"] for r in self.conn.execute(
            "SELECT codice FROM piano_modulo WHERE piano_id = ? ORDER BY ordine",
            (self.piano,),
        )]
        self.assertEqual(["M01", "M02", "M09"], codes)

    def test_it_lands_at_the_end_of_the_plan(self) -> None:
        """The catalogue's own order says nothing about a plan built before it."""
        self._catalogue()
        rules.add_module_to_open_plans(self.conn, "M09")
        last = self.conn.execute(
            "SELECT codice FROM piano_modulo WHERE piano_id = ? ORDER BY ordine DESC LIMIT 1",
            (self.piano,),
        ).fetchone()["codice"]
        self.assertEqual("M09", last)

    def test_running_it_twice_does_not_duplicate(self) -> None:
        self._catalogue()
        rules.add_module_to_open_plans(self.conn, "M09")
        self.assertEqual(0, rules.add_module_to_open_plans(self.conn, "M09"))
        self.assertEqual(
            1,
            self.conn.execute(
                "SELECT COUNT(*) c FROM piano_modulo WHERE piano_id = ? AND codice = 'M09'",
                (self.piano,),
            ).fetchone()["c"],
        )

    def test_a_closed_plan_is_left_alone(self) -> None:
        """A closed plan is a signed document: it does not change underneath."""
        self.conn.execute(
            "UPDATE piano SET chiuso_il = '2026-02-01T09:00:00' WHERE id = ?",
            (self.piano,),
        )
        self.conn.commit()
        self._catalogue()
        self.assertEqual(0, rules.add_module_to_open_plans(self.conn, "M09"))
        self.assertEqual(
            0,
            self.conn.execute(
                "SELECT COUNT(*) c FROM piano_modulo WHERE piano_id = ? AND codice = 'M09'",
                (self.piano,),
            ).fetchone()["c"],
        )

    def test_an_unknown_code_changes_nothing(self) -> None:
        self.assertEqual(0, rules.add_module_to_open_plans(self.conn, "M99"))

    def test_the_new_module_is_applicable_and_still_to_plan(self) -> None:
        """It arrives usable: it has to be schedulable straight away."""
        self._catalogue()
        rules.add_module_to_open_plans(self.conn, "M09")
        row = [m for m in rules.module_summary(self.conn, self.piano)
               if m["codice"] == "M09"][0]
        self.assertEqual("SI", row["applicabile"])
        self.assertEqual("Da pianificare", row["stato"])


class CatalogueAlignmentTests(PlanFixture):
    """Repairing plans that drifted from the catalogue, reported from real use.

    The fixture's plan holds M01 and M02 and no catalogue exists yet, which is
    exactly the shape of an archive created before the catalogue was filled.
    """

    def _catalogue(self, code: str, title: str, area: str = "Generale") -> None:
        self.conn.execute(
            """INSERT INTO modulo_catalogo (codice, area, titolo, modalita_default, ordine)
               VALUES (?, ?, ?, 'Spiegazione', 1)""",
            (code, area, title),
        )
        self.conn.commit()

    def test_a_module_catalogued_before_the_fix_is_recovered(self) -> None:
        """It was out of reach for good: the plan existed, nothing added it."""
        self._catalogue("M09", "Ciclo passivo")
        outcome = rules.align_open_plans_with_catalogue(self.conn)
        self.assertEqual(1, outcome["added"])
        codes = [r["codice"] for r in self.conn.execute(
            "SELECT codice FROM piano_modulo WHERE piano_id = ? ORDER BY ordine",
            (self.piano,),
        )]
        self.assertIn("M09", codes)

    def test_a_renamed_module_reaches_the_plans(self) -> None:
        self._catalogue("M01", "Presentazione rivista")
        outcome = rules.align_open_plans_with_catalogue(self.conn)
        self.assertEqual(1, outcome["updated"])
        self.assertEqual(
            "Presentazione rivista",
            self.conn.execute(
                "SELECT titolo FROM piano_modulo WHERE id = ?", (self.modulo,)
            ).fetchone()["titolo"],
        )

    def test_an_empty_title_is_repaired(self) -> None:
        """The case seen in the field: propagated blank, renamed afterwards."""
        self.conn.execute(
            "UPDATE piano_modulo SET titolo = '' WHERE id = ?", (self.modulo,)
        )
        self.conn.commit()
        self._catalogue("M01", "Presentazione")
        rules.align_open_plans_with_catalogue(self.conn)
        self.assertEqual(
            "Presentazione",
            self.conn.execute(
                "SELECT titolo FROM piano_modulo WHERE id = ?", (self.modulo,)
            ).fetchone()["titolo"],
        )

    def test_per_plan_choices_are_never_overwritten(self) -> None:
        """applicabile, modalita and the tutor are decisions taken on the plan."""
        self.conn.execute(
            """UPDATE piano_modulo SET applicabile = 'NO', modalita = 'Affiancamento',
                   tutor_referente_id = ?, esito = 'OK' WHERE id = ?""",
            (self.tutor, self.modulo),
        )
        self.conn.commit()
        self._catalogue("M01", "Presentazione rivista")
        rules.align_open_plans_with_catalogue(self.conn)

        row = self.conn.execute(
            "SELECT * FROM piano_modulo WHERE id = ?", (self.modulo,)
        ).fetchone()
        self.assertEqual("Presentazione rivista", row["titolo"])   # questo si'
        self.assertEqual("NO", row["applicabile"])                 # questi no
        self.assertEqual("Affiancamento", row["modalita"])
        self.assertEqual(self.tutor, row["tutor_referente_id"])
        self.assertEqual("OK", row["esito"])

    def test_a_closed_plan_is_left_alone(self) -> None:
        self.conn.execute(
            "UPDATE piano SET chiuso_il = '2026-02-01T09:00:00' WHERE id = ?",
            (self.piano,),
        )
        self.conn.commit()
        self._catalogue("M01", "Presentazione rivista")
        outcome = rules.align_open_plans_with_catalogue(self.conn)
        self.assertEqual({"added": 0, "updated": 0}, outcome)
        self.assertEqual(
            "Presentazione",
            self.conn.execute(
                "SELECT titolo FROM piano_modulo WHERE id = ?", (self.modulo,)
            ).fetchone()["titolo"],
        )

    def test_it_is_idempotent(self) -> None:
        """It runs at every start-up: the second time must change nothing."""
        self._catalogue("M09", "Ciclo passivo")
        rules.align_open_plans_with_catalogue(self.conn)
        self.assertEqual(
            {"added": 0, "updated": 0},
            rules.align_open_plans_with_catalogue(self.conn),
        )

    def test_an_empty_catalogue_changes_nothing(self) -> None:
        self.assertEqual(
            {"added": 0, "updated": 0},
            rules.align_open_plans_with_catalogue(self.conn),
        )


class ClosingAPlanTests(PlanFixture):
    """Closing is what makes "a closed plan does not change" reachable at all.

    Before this existed the column was in the schema and the rules honoured it,
    but nothing ever set it: every plan stayed open for ever.
    """

    def test_a_new_plan_is_open(self) -> None:
        self.assertFalse(rules.plan_is_closed(self.conn, self.piano))

    def test_closing_records_when(self) -> None:
        rules.close_plan(self.conn, self.piano, "2026-03-01T10:00:00")
        self.assertTrue(rules.plan_is_closed(self.conn, self.piano))
        self.assertEqual(
            "2026-03-01T10:00:00",
            self.conn.execute(
                "SELECT chiuso_il FROM piano WHERE id = ?", (self.piano,)
            ).fetchone()["chiuso_il"],
        )

    def test_closing_twice_keeps_the_first_date(self) -> None:
        """It records when the plan was declared over, not the last click."""
        first = rules.close_plan(self.conn, self.piano, "2026-03-01T10:00:00")
        again = rules.close_plan(self.conn, self.piano, "2026-06-01T10:00:00")
        self.assertEqual(first, again)

    def test_closing_a_plan_that_does_not_exist(self) -> None:
        self.assertIsNone(rules.close_plan(self.conn, 999, "2026-03-01T10:00:00"))

    def test_reopening_undoes_it(self) -> None:
        rules.close_plan(self.conn, self.piano, "2026-03-01T10:00:00")
        rules.reopen_plan(self.conn, self.piano)
        self.assertFalse(rules.plan_is_closed(self.conn, self.piano))

    def test_a_closed_plan_stops_following_the_catalogue(self) -> None:
        rules.close_plan(self.conn, self.piano, "2026-03-01T10:00:00")
        self.conn.execute(
            """INSERT INTO modulo_catalogo (codice, area, titolo, modalita_default, ordine)
               VALUES ('M09', 'Acquisti', 'Ciclo passivo', 'Spiegazione', 9)"""
        )
        self.conn.commit()
        self.assertEqual(
            {"added": 0, "updated": 0},
            rules.align_open_plans_with_catalogue(self.conn),
        )

    def test_automatic_closing_leaves_a_closed_plan_alone(self) -> None:
        """Otherwise it would mark sessions Svolta inside a signed document."""
        self.conn.execute(
            """INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio,
                                     ora_fine, stato, creata_il, modificata_il)
               VALUES (?, ?, '2026-01-08', '09:00', '11:00', 'Pianificata',
                       '2026-01-01T09:00:00', '2026-01-01T09:00:00')""",
            (self.piano, self.modulo),
        )
        self.conn.commit()

        now = datetime(2026, 1, 20, 9, 0)
        self.assertEqual(1, len(rules.sessions_to_close(self.conn, now)))

        rules.close_plan(self.conn, self.piano, "2026-01-15T10:00:00")
        self.assertEqual([], rules.sessions_to_close(self.conn, now))

        rules.reopen_plan(self.conn, self.piano)
        self.assertEqual(1, len(rules.sessions_to_close(self.conn, now)))


if __name__ == "__main__":
    unittest.main()
