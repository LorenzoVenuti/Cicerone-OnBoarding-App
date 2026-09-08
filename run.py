"""Starting the application: local server plus native window.

This is also the entry point of the packaged app.
"""

import socket
import threading
import traceback
from datetime import datetime

import uvicorn
import webview

from app.main import app
from app.paths import data_folder, template_folder

LOG_PATH = data_folder() / "dati" / "avvio.log"


def log(message: str) -> None:
    """Records the start-up on file.

    The packaged app has no terminal window: without this, a failure at start-up
    would be invisible both to the person using the program and to whoever is
    helping them.
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def free_port(preferred: int = 8731) -> int:
    """Uses the preferred port when it is free, any other one otherwise.

    On a company computer the chosen port may already be taken by something
    else: better to move than to refuse to start.
    """
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port: int) -> uvicorn.Server:
    """Brings the server up on a background thread.

    `uvicorn.run` cannot be used: it installs signal handlers, and those only
    work on the main thread, which here belongs to the window. Off the main
    thread it would fail silently.
    """
    configuration = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(configuration)
    server.install_signal_handlers = lambda: None

    def run() -> None:
        try:
            server.run()
        except Exception:
            log("the server did not start:\n" + traceback.format_exc())

    threading.Thread(target=run, daemon=True).start()
    return server


def wait_for(server: uvicorn.Server, seconds: float = 20) -> bool:
    """Waits for the server to accept connections before opening the window."""
    deadline = datetime.now().timestamp() + seconds
    while datetime.now().timestamp() < deadline:
        if server.started:
            return True
        threading.Event().wait(0.1)
    return False


def main() -> None:
    try:
        # Copy the templates next to the app on first run, so whoever uses the
        # program finds them and can edit them without waiting for a first
        # message to be sent.
        template_folder()
        port = free_port()
        server = start_server(port)
        if not wait_for(server):
            log("the server did not answer within the expected time")
            return
        log(f"started on port {port}")
        webview.create_window(
            "Cicerone",
            f"http://127.0.0.1:{port}",
            width=1360,
            height=880,
            min_size=(1024, 640),
        )
        webview.start()
    except Exception:
        log("error while starting:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
