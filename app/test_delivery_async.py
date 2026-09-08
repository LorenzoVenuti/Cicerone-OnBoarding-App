"""Waiting on the mail program must not stop the application.

When a message does not go out, the app waits for it to leave the outbox: up to
half a minute. If that wait happens on the event loop, the interface is frozen
for the whole time and somebody filling in a session believes the program has
crashed. This measures that it does not happen.
"""

import asyncio
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, delivery

MESSAGGIO = {
    "tipo": "nuova",
    "sessione_id": None,   # no real session: what is measured here is only the wait
    "oggetto": "Convocazione",
    "corpo": "testo",
    "destinatari": ["mario@esempio.test"],
    "senza_email": [],
}

RITARDO = 0.4      # quanto ci mette il finto programma di posta
PASSO = 0.02       # how often the interface would like to answer


class SlowChannel:
    """A mail program that takes a while, as when it cannot send."""

    name = "lento"

    def __init__(self, delay: float = RITARDO) -> None:
        self.delay = delay
        self.chiamate = 0

    def send(self, messaggio: dict) -> None:
        self.chiamate += 1
        time.sleep(self.delay)


async def _giri_durante(avvia_lavoro) -> int:
    """How many times the event loop gets to run while the work is in progress.

    It measures how alive the interface stays: if the loop is blocked, no other
    request is served.

    The measuring window is fixed *before* the work starts, otherwise a blocking
    job would finish first and the counting would happen afterwards, on an idle
    loop: it would measure nothing.
    """
    scadenza = time.monotonic() + RITARDO
    giri = 0

    async def battito() -> None:
        nonlocal giri
        while time.monotonic() < scadenza:
            await asyncio.sleep(PASSO)
            giri += 1

    compito = asyncio.create_task(battito())
    await asyncio.sleep(0)          # let the heartbeat get going
    await avvia_lavoro()
    await compito
    return giri


class NonBlockingDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.initialise(Path(self.cartella) / "prova.db")
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "1")
        self.canale = SlowChannel()

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def test_the_interface_stays_alive_during_a_slow_send(self) -> None:
        async def prova() -> int:
            with patch("app.delivery.choose_channel", return_value=self.canale):
                return await _giri_durante(
                    lambda: delivery.send_without_blocking(self.conn, dict(MESSAGGIO))
                )

        giri = asyncio.run(prova())
        # unblocked, the loop turns many times; a few are enough to prove it
        self.assertGreater(giri, 5)
        self.assertEqual(self.canale.chiamate, 1)

    def test_the_sync_version_does_block(self) -> None:
        """Documents why the asynchronous version exists."""
        async def prova() -> int:
            async def sincrona() -> None:
                with patch("app.delivery.choose_channel", return_value=self.canale):
                    delivery.send(self.conn, dict(MESSAGGIO))
            return await _giri_durante(sincrona)

        self.assertLessEqual(asyncio.run(prova()), 2)

    def test_the_outcome_is_recorded_as_in_the_sync_version(self) -> None:
        async def prova() -> dict:
            with patch("app.delivery.choose_channel", return_value=self.canale):
                return await delivery.send_without_blocking(self.conn, dict(MESSAGGIO))

        esito = asyncio.run(prova())
        self.assertEqual(esito["esito"], "inviata")
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["esito"], "inviata")
        self.assertIsNotNone(voce["inviata_il"])

    def test_a_mail_program_error_is_recorded(self) -> None:
        rotto = SlowChannel(delay=0)
        rotto.send = lambda messaggio: (_ for _ in ()).throw(
            delivery.DeliveryError("non e' partita")
        )

        async def prova() -> dict:
            with patch("app.delivery.choose_channel", return_value=rotto):
                return await delivery.send_without_blocking(self.conn, dict(MESSAGGIO))

        esito = asyncio.run(prova())
        self.assertEqual(esito["esito"], "errore")
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["esito"], "errore")
        self.assertIsNone(voce["inviata_il"])

    def test_with_delivery_off_the_mail_program_is_not_called(self) -> None:
        db.save_setting(self.conn, db.KEY_AUTO_EMAIL, "0")

        async def prova() -> dict:
            with patch("app.delivery.choose_channel", return_value=self.canale):
                return await delivery.send_without_blocking(self.conn, dict(MESSAGGIO))

        esito = asyncio.run(prova())
        self.assertEqual(esito["esito"], "invio_disattivato")
        self.assertEqual(self.canale.chiamate, 0)


if __name__ == "__main__":
    unittest.main()
