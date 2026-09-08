"""Avvio dell'applicazione: server locale piu' finestra nativa.

E' anche il punto d'ingresso dell'eseguibile Windows.
"""

import socket
import threading
import traceback
from datetime import datetime

import uvicorn
import webview

from app.main import app
from app.percorsi import cartella_dati, cartella_template

PERCORSO_LOG = cartella_dati() / "dati" / "avvio.log"


def registra(messaggio: str) -> None:
    """Traccia l'avvio su file.

    Nell'eseguibile non c'e' finestra di terminale: senza questo, un errore in
    partenza sarebbe invisibile a chi usa il programma e a chi lo assiste.
    """
    PERCORSO_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PERCORSO_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {messaggio}\n")


def porta_libera(preferita: int = 8731) -> int:
    """Usa la porta preferita se e' libera, altrimenti una qualsiasi.

    Su un computer aziendale la porta scelta puo' essere gia' occupata da
    altro: meglio spostarsi che rifiutarsi di partire.
    """
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferita))
            return preferita
        except OSError:
            pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def avvia_server(porta: int) -> uvicorn.Server:
    """Fa partire il server in un thread secondario.

    Non si puo' usare `uvicorn.run`: installa dei gestori di segnale, e quelli
    funzionano solo nel thread principale, che qui serve alla finestra. Fuori
    dal thread principale fallirebbe in silenzio.
    """
    configurazione = uvicorn.Config(
        app, host="127.0.0.1", port=porta, log_level="warning"
    )
    server = uvicorn.Server(configurazione)
    server.install_signal_handlers = lambda: None

    def esegui() -> None:
        try:
            server.run()
        except Exception:
            registra("il server non e' partito:\n" + traceback.format_exc())

    threading.Thread(target=esegui, daemon=True).start()
    return server


def attendi(server: uvicorn.Server, secondi: float = 20) -> bool:
    """Aspetta che il server accetti connessioni prima di aprire la finestra."""
    scadenza = datetime.now().timestamp() + secondi
    while datetime.now().timestamp() < scadenza:
        if server.started:
            return True
        threading.Event().wait(0.1)
    return False


def main() -> None:
    try:
        # Copia i template accanto all'eseguibile al primo avvio, cosi' chi usa
        # il programma li trova e puo' modificarli senza aspettare la prima mail.
        cartella_template()
        porta = porta_libera()
        server = avvia_server(porta)
        if not attendi(server):
            registra("il server non ha risposto entro il tempo previsto")
            return
        registra(f"avviato sulla porta {porta}")
        webview.create_window(
            "Piano Formazione",
            f"http://127.0.0.1:{porta}",
            width=1360,
            height=880,
            min_size=(1024, 640),
        )
        webview.start()
    except Exception:
        registra("errore in avvio:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
