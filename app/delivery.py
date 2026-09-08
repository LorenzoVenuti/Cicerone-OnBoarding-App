"""Sending the notifications through the mail program already set up.

The idea is the same on both platforms: drive the Outlook that whoever uses the
app has already installed and signed in. No credentials to keep, no SMTP, no
service mailbox to request from IT, and the message goes out from the person.

Two lessons learned by actually trying it, which explain how this file is built:

**The channel is not guessed.** A Mac can have both Outlook and Mail, one set up
and the other empty, and from the outside they look alike: Outlook's profile can
weigh hundreds of megabytes without holding a single active account. So the
channel is not deduced, it is **chosen once during setup** and stored.
`available_channels` feeds that screen: it really asks the programs which
addresses they hold.

**"No error" does not mean "sent".** AppleScript reports success even when the
message is merely queued, or when the client accepts it and loses it because it
has no account. Recording that as a delivery is the worst possible defect for an
application whose job is to warn people: the log would say "sent" and nobody
would ever learn otherwise. That is why, after `send`, we check that the message
**actually left the outbox**, and if it is still sitting there it counts as an
error.
"""

import asyncio
import platform
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import db
from .paths import data_folder

DRAFTS_FOLDER = data_folder() / "dati" / "mail_non_inviate"

# Seconds to wait for the client to take the message out of the outbox: past
# this, it counts as not sent.
DELIVERY_WAIT = 30


class DeliveryError(RuntimeError):
    pass


@contextmanager
def invitation_file(content: str | None):
    """Writes the invitation to a temporary file, just long enough to attach it.

    Mail programs attach from disk, not from memory. The file name is what the
    recipient sees: `invito.ics` reads clearly.
    """
    if not content:
        yield ""
        return
    folder = Path(tempfile.mkdtemp(prefix="cicerone-"))
    path = folder / "invito.ics"
    path.write_text(content, encoding="utf-8")
    try:
        yield str(path)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _osascript(script: str, arguments: list[str], timeout: int = 60) -> str:
    """Runs AppleScript passing the data as arguments, not inside the source.

    Subject and body contain quotes, apostrophes and newlines: pasted into the
    script they would break it or, worse, be interpreted as code.
    """
    try:
        result = subprocess.run(
            ["osascript", "-", *arguments],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise DeliveryError(
            "il programma di posta non ha risposto in tempo: puo' esserci una "
            "finestra aperta in attesa di risposta."
        ) from error
    except OSError as error:
        raise DeliveryError(str(error)) from error

    if result.returncode != 0:
        raise DeliveryError(_explain(result.stderr.strip()))
    return result.stdout.strip()


def _explain(error: str) -> str:
    """Turns osascript errors into something you can act on."""
    if "NO_ACCOUNT" in error:
        return (
            "il programma di posta non ha nessun account configurato: "
            "va aggiunto l'indirizzo di lavoro prima di inviare."
        )
    if "STUCK_IN_OUTBOX" in error:
        return (
            "il messaggio e' rimasto nella posta in uscita e non e' partito: "
            "il programma di posta non riesce a spedire (account da "
            "riautenticare, oppure offline)."
        )
    if "-1743" in error or "not authori" in error.lower():
        return (
            "macOS non ha concesso il permesso di controllare il programma di "
            "posta. Va abilitato in System Settings > Privacy & Security > "
            f"Automation. ({error})"
        )
    if "-600" in error or "-1728" in error:
        return f"il programma di posta non risponde. ({error})"
    return error or "osascript non ha riportato l'errore"


class OutlookWindows:
    """Sending through the Outlook installed on Windows (COM)."""

    name = "outlook"
    label = "Outlook (Windows)"

    def __init__(self, sender: str | None = None) -> None:
        self.sender = sender

    def available(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import win32com.client  # noqa: F401
            return True
        except ImportError:
            return False

    def accounts(self) -> list[str]:
        return []

    def send(self, message: dict) -> None:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # olMailItem
            mail.To = "; ".join(message["destinatari"])
            mail.Subject = message["oggetto"]
            mail.Body = message["corpo"]
            with invitation_file(message.get("calendario")) as invitation:
                if invitation:
                    mail.Attachments.Add(invitation)
                mail.Send()
        except Exception as error:  # the COM API has no useful typed exceptions
            raise DeliveryError(str(error)) from error
        finally:
            pythoncom.CoUninitialize()


class _AppleScriptChannel:
    """What the Mac's two mail programs have in common.

    Subclasses only change the two scripts: Mail's dialect of AppleScript and
    Outlook's do not match.
    """

    name = ""
    label = ""
    PATHS: tuple[Path, ...] = ()
    ACCOUNTS_SCRIPT = ""
    SEND_SCRIPT = ""

    def __init__(self, sender: str | None = None) -> None:
        self.sender = sender

    def available(self) -> bool:
        """Only whether the program is installed: this check must stay cheap.

        Knowing whether it actually holds an account means asking it, which
        means launching it: that happens in `accounts()`, during setup, not on
        every page load.
        """
        if platform.system() != "Darwin":
            return False
        return any(path.exists() for path in self.PATHS)

    def accounts(self) -> list[str]:
        """Addresses usable as sender. Launches the mail program."""
        if not self.available():
            return []
        try:
            output = _osascript(self.ACCOUNTS_SCRIPT, [], timeout=60)
        except DeliveryError:
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]

    def send(self, message: dict) -> None:
        if not message["destinatari"]:
            raise DeliveryError("nessun destinatario")
        with invitation_file(message.get("calendario")) as invitation:
            _osascript(
                self.SEND_SCRIPT,
                [
                    message["oggetto"],
                    message["corpo"],
                    self.sender or "",
                    invitation,
                    *message["destinatari"],
                ],
                timeout=DELIVERY_WAIT + 60,
            )


class AppleMail(_AppleScriptChannel):
    """Sending through Mail, the macOS mail application."""

    name = "mail_mac"
    label = "Mail (macOS)"

    PATHS = (
        Path("/System/Applications/Mail.app"),
        Path("/Applications/Mail.app"),
    )

    # The addresses are gathered into a list and joined at the end:
    # concatenating them inside the loop yields references, not text.
    ACCOUNTS_SCRIPT = """
set found to {}
tell application "Mail"
    repeat with a in accounts
        try
            if enabled of a then set found to found & (email addresses of a)
        end try
    end repeat
end tell
set AppleScript's text item delimiters to linefeed
return found as text
"""

    # `content` in Mail is the plain text: the templates are text files.
    SEND_SCRIPT = """
on run argv
    set theSubject to item 1 of argv
    set theBody to item 2 of argv
    set theSender to item 3 of argv
    set theInvitation to item 4 of argv
    tell application "Mail"
        if (count of accounts) is 0 then error "NO_ACCOUNT" number 1001
        if theSender is "" then
            set theMessage to make new outgoing message with properties ¬
                {subject:theSubject, content:theBody, visible:false}
        else
            set theMessage to make new outgoing message with properties ¬
                {subject:theSubject, content:theBody, sender:theSender, visible:false}
        end if
        tell theMessage
            repeat with i from 5 to (count of argv)
                make new to recipient with properties {address:(item i of argv)}
            end repeat
            if theInvitation is not "" then
                make new attachment with properties ¬
                    {file name:(POSIX file theInvitation)} at after the last paragraph of content
            end if
        end tell
        set theId to id of theMessage
        send theMessage
        -- "send" accepts the message, it does not deliver it: while it sits in
        -- the outbox, nothing has gone anywhere.
        repeat WAIT times
            delay 1
            set stillThere to false
            repeat with m in (every outgoing message)
                try
                    if (id of m) is theId then set stillThere to true
                end try
            end repeat
            if not stillThere then return "sent"
        end repeat
        error "STUCK_IN_OUTBOX" number 1002
    end tell
end run
"""

    def __init__(self, sender: str | None = None) -> None:
        super().__init__(sender)
        self.SEND_SCRIPT = self.SEND_SCRIPT.replace("WAIT", str(DELIVERY_WAIT))


class OutlookMac(_AppleScriptChannel):
    """Sending through the Outlook installed on the Mac.

    Careful: recent versions of Outlook for Mac have reduced AppleScript
    support and can report zero accounts while holding a profile on disk. That
    is why counting the accounts is not a detail but a condition: without one,
    the message would be accepted and lost.
    """

    name = "outlook_mac"
    label = "Outlook (Mac)"

    PATHS = (
        Path("/Applications/Microsoft Outlook.app"),
        Path.home() / "Applications" / "Microsoft Outlook.app",
    )

    ACCOUNTS_SCRIPT = """
set found to {}
tell application "Microsoft Outlook"
    repeat with a in exchange accounts
        try
            set found to found & (email address of a)
        end try
    end repeat
    repeat with a in imap accounts
        try
            set found to found & (email address of a)
        end try
    end repeat
    repeat with a in pop accounts
        try
            set found to found & (email address of a)
        end try
    end repeat
end tell
set AppleScript's text item delimiters to linefeed
return found as text
"""

    # `content` in Outlook is HTML: plain text would lose its line breaks, so
    # `plain text content` is the right field.
    SEND_SCRIPT = """
on run argv
    set theSubject to item 1 of argv
    set theBody to item 2 of argv
    set theInvitation to item 4 of argv
    tell application "Microsoft Outlook"
        set howMany to (count of exchange accounts) + (count of imap accounts) ¬
            + (count of pop accounts)
        if howMany is 0 then error "NO_ACCOUNT" number 1001
        set theMessage to make new outgoing message with properties ¬
            {subject:theSubject, plain text content:theBody}
        repeat with i from 5 to (count of argv)
            make new to recipient at theMessage with properties ¬
                {email address:{address:(item i of argv)}}
        end repeat
        if theInvitation is not "" then
            make new attachment at theMessage with properties {file:(POSIX file theInvitation)}
        end if
        send theMessage
        repeat WAIT times
            delay 1
            if (count of messages of outbox) is 0 then return "sent"
        end repeat
        error "STUCK_IN_OUTBOX" number 1002
    end tell
end run
"""

    def __init__(self, sender: str | None = None) -> None:
        super().__init__(sender)
        self.SEND_SCRIPT = self.SEND_SCRIPT.replace("WAIT", str(DELIVERY_WAIT))


class FileFallback:
    """Last resort: writes the message down instead of sending it.

    This is not a delivery channel and must not be chosen by mistake: it exists
    for when there is no mail program at all, so the message lands on disk
    rather than being lost.
    """

    name = "file"
    label = "Salva su file (non spedisce)"

    def __init__(self, sender: str | None = None) -> None:
        self.sender = sender

    def available(self) -> bool:
        return True

    def accounts(self) -> list[str]:
        return []

    def send(self, message: dict) -> None:
        DRAFTS_FOLDER.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = DRAFTS_FOLDER / f"{stamp}-{message['tipo']}-{message['sessione_id']}.txt"
        path.write_text(
            f"A: {'; '.join(message['destinatari'])}\n"
            f"Oggetto: {message['oggetto']}\n\n{message['corpo']}\n",
            encoding="utf-8",
        )
        if message.get("calendario"):
            path.with_suffix(".ics").write_text(
                message["calendario"], encoding="utf-8"
            )


# In order of preference: the real mail programs first.
CHANNELS = (OutlookWindows, AppleMail, OutlookMac, FileFallback)


def channel_by_name(name: str, sender: str | None = None):
    for channel_class in CHANNELS:
        if channel_class.name == name:
            return channel_class(sender)
    return None


def available_channels() -> list[dict]:
    """What is on this computer, by actually asking it.

    This feeds the setup screen: it lists the mail programs present and the
    addresses they hold, so the choice is made by the person using the app
    instead of being guessed by the program.
    """
    found = []
    for channel_class in CHANNELS:
        channel = channel_class()
        if not channel.available():
            continue
        addresses = channel.accounts()
        found.append(
            {
                "nome": channel.name,
                "etichetta": channel.label,
                "account": addresses,
                "pronto": bool(addresses) or channel.name in {"file", "outlook"},
            }
        )
    return found


def choose_channel(conn: sqlite3.Connection | None = None):
    """The channel to use: the configured one, when there is one.

    Without a stored choice it falls back to the first program present, which is
    only a reasonable default: the setup exists precisely because "present" and
    "working" are not the same thing.
    """
    if conn is not None:
        chosen = db.read_setting(conn, db.KEY_MAIL_CHANNEL)
        if chosen:
            channel = channel_by_name(
                chosen, db.read_setting(conn, db.KEY_MAIL_SENDER)
            )
            if channel is not None:
                return channel

    for channel_class in CHANNELS:
        channel = channel_class()
        if channel.available():
            return channel
    return FileFallback()


def _policy(
    conn: sqlite3.Connection, message: dict, mail_log_id: int | None
) -> dict | None:
    """The reasons not to send that can be decided without asking anyone."""
    from . import messages

    if not db.automatic_email_delivery(conn):
        messages.record(conn, message, "invio_disattivato", mail_log_id=mail_log_id)
        return {
            "esito": "invio_disattivato",
            "senza_email": message["senza_email"],
        }

    if not message["destinatari"]:
        messages.record(
            conn, message, "senza_destinatari", mail_log_id=mail_log_id
        )
        return {"esito": "senza_destinatari", "senza_email": message["senza_email"]}
    return None


def _record_outcome(
    conn: sqlite3.Connection,
    message: dict,
    channel,
    error: Exception | None,
    mail_log_id: int | None,
) -> dict:
    from . import messages

    if error is not None:
        messages.record(
            conn, message, "errore", str(error), mail_log_id=mail_log_id
        )
        return {"esito": "errore", "errore": str(error)}

    messages.record(conn, message, "inviata", mail_log_id=mail_log_id)
    # It may have reached only some of the people: whoever has no address must
    # be flagged, or the omission goes unnoticed.
    return {
        "esito": "inviata",
        "canale": channel.name,
        "senza_email": message["senza_email"],
    }


def send(
    conn: sqlite3.Connection,
    message: dict,
    mail_log_id: int | None = None,
) -> dict:
    """Applies the delivery policy, sends when allowed, records the outcome.

    Blocks until the mail program is done. Inside an endpoint use
    `send_without_blocking`.
    """
    blocked = _policy(conn, message, mail_log_id)
    if blocked is not None:
        return blocked

    channel = choose_channel(conn)
    error = None
    try:
        channel.send(message)
    except Exception as problem:
        error = problem
    return _record_outcome(conn, message, channel, error, mail_log_id)


async def send_without_blocking(
    conn: sqlite3.Connection,
    message: dict,
    mail_log_id: int | None = None,
) -> dict:
    """Like `send`, but without freezing the whole application.

    Waiting for the message to leave the outbox can take tens of seconds, and
    precisely when something is wrong: inside the event loop the interface would
    sit frozen for all that time, and whoever is filling in a session would
    think the app had crashed. Here only the waiting goes to a thread.

    Writing to the log stays on this thread: the SQLite connection is shared and
    tied to the event loop, and using it elsewhere would raise "SQLite objects
    created in a thread can only be used in that same thread".
    """
    blocked = _policy(conn, message, mail_log_id)
    if blocked is not None:
        return blocked

    channel = choose_channel(conn)
    error = None
    try:
        await asyncio.to_thread(channel.send, message)
    except Exception as problem:
        error = problem
    return _record_outcome(conn, message, channel, error, mail_log_id)
