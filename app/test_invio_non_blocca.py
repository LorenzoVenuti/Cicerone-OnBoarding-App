"""L'attesa del programma di posta non deve fermare l'applicazione.

Quando una mail non parte, l'app aspetta che il messaggio esca dalla coda: fino
a mezzo minuto. Se quell'attesa avviene nell'event loop, l'interfaccia resta
ferma per tutto il tempo e chi sta compilando una sessione crede che il
programma si sia piantato. Qui si misura che non succeda.
"""

import asyncio
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, invio

MESSAGGIO = {
    "tipo": "nuova",
    "sessione_id": None,   # nessuna sessione vera: qui si misura solo l attesa
    "oggetto": "Convocazione",
    "corpo": "testo",
    "destinatari": ["mario@esempio.test"],
    "senza_email": [],
}

RITARDO = 0.4      # quanto ci mette il finto programma di posta
PASSO = 0.02       # ogni quanto l'interfaccia vorrebbe rispondere


class CanaleLento:
    """Un programma di posta che ci mette un po', come quando non spedisce."""

    nome = "lento"

    def __init__(self, ritardo: float = RITARDO) -> None:
        self.ritardo = ritardo
        self.chiamate = 0

    def invia(self, messaggio: dict) -> None:
        self.chiamate += 1
        time.sleep(self.ritardo)


async def _giri_durante(avvia_lavoro) -> int:
    """Quante volte l'event loop riesce a girare mentre il lavoro e' in corso.

    E' la misura di quanto l'interfaccia resta viva: se il loop e' bloccato,
    nessun'altra richiesta viene servita.

    La finestra di misura si fissa *prima* di far partire il lavoro, altrimenti
    un lavoro bloccante finirebbe per primo e il conteggio avverrebbe dopo, a
    loop ormai libero: si misurerebbe il nulla.
    """
    scadenza = time.monotonic() + RITARDO
    giri = 0

    async def battito() -> None:
        nonlocal giri
        while time.monotonic() < scadenza:
            await asyncio.sleep(PASSO)
            giri += 1

    compito = asyncio.create_task(battito())
    await asyncio.sleep(0)          # lascia che il battito cominci
    await avvia_lavoro()
    await compito
    return giri


class InvioNonBloccanteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cartella = tempfile.mkdtemp()
        self.conn = db.inizializza(Path(self.cartella) / "prova.db")
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "1")
        self.canale = CanaleLento()

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.cartella, ignore_errors=True)

    def test_l_interfaccia_resta_viva_durante_un_invio_lento(self) -> None:
        async def prova() -> int:
            with patch("app.invio.scegli_canale", return_value=self.canale):
                return await _giri_durante(
                    lambda: invio.invia_senza_bloccare(self.conn, dict(MESSAGGIO))
                )

        giri = asyncio.run(prova())
        # senza blocco il loop gira molte volte; ne bastano poche per provarlo
        self.assertGreater(giri, 5)
        self.assertEqual(self.canale.chiamate, 1)

    def test_la_versione_sincrona_invece_blocca(self) -> None:
        """Documenta perche' esiste la versione asincrona."""
        async def prova() -> int:
            async def sincrona() -> None:
                with patch("app.invio.scegli_canale", return_value=self.canale):
                    invio.invia(self.conn, dict(MESSAGGIO))
            return await _giri_durante(sincrona)

        self.assertLessEqual(asyncio.run(prova()), 2)

    def test_l_esito_viene_registrato_come_nella_versione_sincrona(self) -> None:
        async def prova() -> dict:
            with patch("app.invio.scegli_canale", return_value=self.canale):
                return await invio.invia_senza_bloccare(self.conn, dict(MESSAGGIO))

        esito = asyncio.run(prova())
        self.assertEqual(esito["esito"], "inviata")
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["esito"], "inviata")
        self.assertIsNotNone(voce["inviata_il"])

    def test_un_errore_del_programma_di_posta_viene_registrato(self) -> None:
        rotto = CanaleLento(ritardo=0)
        rotto.invia = lambda messaggio: (_ for _ in ()).throw(
            invio.ErroreInvio("non e' partita")
        )

        async def prova() -> dict:
            with patch("app.invio.scegli_canale", return_value=rotto):
                return await invio.invia_senza_bloccare(self.conn, dict(MESSAGGIO))

        esito = asyncio.run(prova())
        self.assertEqual(esito["esito"], "errore")
        voce = self.conn.execute("SELECT * FROM mail_log").fetchone()
        self.assertEqual(voce["esito"], "errore")
        self.assertIsNone(voce["inviata_il"])

    def test_con_invio_spento_non_si_chiama_il_programma_di_posta(self) -> None:
        db.salva_impostazione(self.conn, db.CHIAVE_INVIO_EMAIL_AUTOMATICO, "0")

        async def prova() -> dict:
            with patch("app.invio.scegli_canale", return_value=self.canale):
                return await invio.invia_senza_bloccare(self.conn, dict(MESSAGGIO))

        esito = asyncio.run(prova())
        self.assertEqual(esito["esito"], "invio_disattivato")
        self.assertEqual(self.canale.chiamate, 0)


if __name__ == "__main__":
    unittest.main()
