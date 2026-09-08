"""Tests for the calendar invitations.

The real risk is not that an invitation fails to arrive: it is that a move or a
cancellation lands on the wrong appointment, deleting from somebody's calendar a
meeting that is in fact going ahead. That is what this file tests.
"""

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import db, invites, messages


def field(text: str, name: str) -> str:
    """The value of one invitation line, rejoining the folded ones."""
    unfolded = text.replace("\r\n ", "")
    for line in unfolded.split("\r\n"):
        if line.startswith(f"{name}:"):
            return line.split(":", 1)[1]
    return ""


class FormatTests(unittest.TestCase):
    def _invitation(self, **changes) -> str:
        parameters = {
            "uid": "abc@cicerone",
            "sequence": 0,
            "day": "2026-09-10",
            "start_time": "09:30",
            "end_time": "11:30",
            "title": "Formazione: M05 - Qualita' e ambiente",
            "description": "Modulo: M05\nTutor: Anna Bianchi",
            "organiser": "hr@esempio.test",
            "attendees": [{"nome": "Anna Bianchi", "email": "anna@esempio.test"}],
        }
        parameters.update(changes)
        return invites.compose(**parameters)

    def test_it_is_an_invitation_not_a_reminder(self) -> None:
        text = self._invitation()
        self.assertIn("METHOD:REQUEST", text)
        self.assertIn("BEGIN:VEVENT", text)
        self.assertIn("ATTENDEE", text)
        self.assertIn("mailto:anna@esempio.test", text)

    def test_times_travel_in_utc(self) -> None:
        """Without an explicit time zone the appointment would fall at the wrong hour."""
        text = self._invitation()
        expected = (
            datetime(2026, 9, 10, 9, 30, tzinfo=ZoneInfo("Europe/Rome"))
            .astimezone(ZoneInfo("UTC"))
            .strftime("%Y%m%dT%H%M%SZ")
        )
        self.assertEqual(field(text, "DTSTART"), expected)

    def test_special_characters_do_not_break_the_invitation(self) -> None:
        text = self._invitation(title="Riunione; con, virgole\ne a capo")
        self.assertIn("SUMMARY:Riunione\\; con\\, virgole\\ne a capo", text)

    def test_long_lines_are_folded(self) -> None:
        text = self._invitation(description="x" * 300)
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_an_attendee_without_an_address_is_skipped(self) -> None:
        text = self._invitation(
            attendees=[
                {"nome": "Senza Posta", "email": ""},
                {"nome": "Anna", "email": "anna@esempio.test"},
            ]
        )
        self.assertEqual(text.count("ATTENDEE"), 1)

    def test_a_cancellation_targets_the_same_appointment(self) -> None:
        cancellation = self._invitation(sequence=3, cancelled=True)
        self.assertIn("METHOD:CANCEL", cancellation)
        self.assertIn("STATUS:CANCELLED", cancellation)
        self.assertEqual(field(cancellation, "UID"), "abc@cicerone")

    def test_every_appointment_gets_a_different_identifier(self) -> None:
        self.assertNotEqual(invites.new_uid(), invites.new_uid())


class PlanAppointmentTests(unittest.TestCase):
    """The case that matters: several meetings between the same people."""

    def setUp(self) -> None:
        self.folder = tempfile.mkdtemp()
        self.conn = db.initialise(Path(self.folder) / "prova.db")
        c = self.conn

        trainee_person = c.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Anna', 'Bianchi', 'anna@esempio.test')"
        ).lastrowid
        self.tutor = c.execute(
            "INSERT INTO persona (nome, cognome, email) VALUES ('Marco', 'Verdi', 'marco@esempio.test')"
        ).lastrowid
        trainee = c.execute(
            "INSERT INTO risorsa (persona_id, data_inizio) VALUES (?, '2026-01-07')",
            (trainee_person,),
        ).lastrowid
        self.plan = c.execute(
            "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, '2026-01-01T09:00:00')",
            (trainee,),
        ).lastrowid
        self.module = c.execute(
            """INSERT INTO piano_modulo (piano_id, codice, area, titolo, applicabile, ordine)
               VALUES (?, 'M05', 'Sistemi', 'Qualita e ambiente', 'SI', 1)""",
            (self.plan,),
        ).lastrowid
        c.commit()

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.folder, ignore_errors=True)

    def session(self, day: str, start: str = "09:00", end: str = "11:00") -> int:
        session_id = self.conn.execute(
            """INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio,
                                     ora_fine, stato, creata_il, modificata_il)
               VALUES (?, ?, ?, ?, ?, 'Pianificata', '2026-01-01T09:00:00', '2026-01-01T09:00:00')""",
            (self.plan, self.module, day, start, end),
        ).lastrowid
        self.conn.execute(
            "INSERT INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
            (session_id, self.tutor),
        )
        self.conn.commit()
        return session_id

    def test_two_meetings_between_the_same_people_stay_distinct(self) -> None:
        """The delicate part: moving or cancelling one must not touch the other."""
        first = self.session("2026-09-10")
        second = self.session("2026-09-17")

        one = messages.compose(self.conn, first, "nuova")
        two = messages.compose(self.conn, second, "nuova")

        self.assertNotEqual(
            field(one["calendario"], "UID"), field(two["calendario"], "UID")
        )

        # only the first one is cancelled
        cancellation = messages.compose(self.conn, first, "annullamento")
        self.assertIn("METHOD:CANCEL", cancellation["calendario"])
        self.assertEqual(
            field(cancellation["calendario"], "UID"), field(one["calendario"], "UID")
        )
        self.assertNotEqual(
            field(cancellation["calendario"], "UID"), field(two["calendario"], "UID")
        )

    def test_moving_updates_the_same_appointment(self) -> None:
        """It is not cancelled and recreated: the existing one is moved."""
        session_id = self.session("2026-09-10")
        before = messages.compose(self.conn, session_id, "nuova")

        self.conn.execute(
            "UPDATE sessione SET data = '2026-09-24' WHERE id = ?", (session_id,)
        )
        self.conn.commit()
        after = messages.compose(self.conn, session_id, "spostamento")

        self.assertEqual(
            field(before["calendario"], "UID"), field(after["calendario"], "UID")
        )
        self.assertIn("METHOD:REQUEST", after["calendario"])
        self.assertIn("20260924", field(after["calendario"], "DTSTART"))

    def test_the_sequence_rises_with_every_notification(self) -> None:
        """Without a higher sequence, calendars discard the update."""
        session_id = self.session("2026-09-10")
        before = messages.compose(self.conn, session_id, "nuova")
        second_one = messages.compose(self.conn, session_id, "spostamento")
        third_one = messages.compose(self.conn, session_id, "annullamento")

        self.assertEqual(field(before["calendario"], "SEQUENCE"), "0")
        self.assertEqual(field(second_one["calendario"], "SEQUENCE"), "1")
        self.assertEqual(field(third_one["calendario"], "SEQUENCE"), "2")

    def test_the_identifier_never_changes(self) -> None:
        session_id = self.session("2026-09-10")
        messages.compose(self.conn, session_id, "nuova")
        stored = self.conn.execute(
            "SELECT uid_calendario FROM sessione WHERE id = ?", (session_id,)
        ).fetchone()["uid_calendario"]

        messages.compose(self.conn, session_id, "spostamento")
        again = self.conn.execute(
            "SELECT uid_calendario FROM sessione WHERE id = ?", (session_id,)
        ).fetchone()["uid_calendario"]
        self.assertEqual(stored, again)

    def test_attendees_are_the_tutors_and_the_trainee(self) -> None:
        session_id = self.session("2026-09-10")
        invitation = messages.compose(self.conn, session_id, "nuova")["calendario"]
        self.assertIn("mailto:marco@esempio.test", invitation)
        self.assertIn("mailto:anna@esempio.test", invitation)

    def test_the_invitation_is_kept_in_the_log(self) -> None:
        """A retry must resend the same appointment, not a new one."""
        session_id = self.session("2026-09-10")
        message = messages.compose(self.conn, session_id, "nuova")
        messages.record(self.conn, message, "errore", "finto guasto")

        row = self.conn.execute("SELECT * FROM mail_log").fetchone()
        rebuilt = messages.message_from_log(row)
        self.assertEqual(rebuilt["calendario"], message["calendario"])


if __name__ == "__main__":
    unittest.main()
