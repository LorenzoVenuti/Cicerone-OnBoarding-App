"""Composing the notification messages and their calendar invitations.

The templates live in `template_mail/`, as plain text files that can be reworded
without touching the code: the first line is the subject, the rest is the body.

Two sets of names stay in Italian on purpose. The **template variables**
(`{{ risorsa }}`, `{{ data_estesa }}`...) are the contract with those template
files, which are product content written for Italian readers; and the
**dictionary keys** mirror the columns of `mail_log`. Renaming either would
leave code, data and templates disagreeing.
"""

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime

from jinja2 import Template

from . import invites
from .paths import template_folder

DAYS = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
MONTHS = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def long_date(iso: str) -> str:
    """'2026-09-07' -> 'lunedi 7 settembre 2026'."""
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def _load_template(kind: str) -> tuple[Template, Template]:
    text = (template_folder() / f"{kind}.txt").read_text(encoding="utf-8")
    first_line, _, body = text.partition("\n")
    subject = first_line.removeprefix("OGGETTO:").strip()
    return Template(subject), Template(body.strip())


def session_context(conn: sqlite3.Connection, session_id: int) -> dict:
    session = conn.execute(
        """
        SELECT s.*, pm.codice, pm.titolo AS modulo_titolo, pm.area,
               pr.nome AS risorsa_nome, pr.cognome AS risorsa_cognome, pr.email AS risorsa_email
        FROM sessione s
        LEFT JOIN piano_modulo pm ON pm.id = s.piano_modulo_id
        JOIN piano p    ON p.id = s.piano_id
        JOIN risorsa r  ON r.id = p.risorsa_id
        JOIN persona pr ON pr.id = r.persona_id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    if session is None:
        raise ValueError(f"session {session_id} does not exist")

    tutors = conn.execute(
        """
        SELECT p.id, p.nome, p.cognome, p.email
        FROM sessione_tutor st JOIN persona p ON p.id = st.persona_id
        WHERE st.sessione_id = ?
        ORDER BY p.cognome
        """,
        (session_id,),
    ).fetchall()

    module = (
        f"{session['codice']} - {session['modulo_titolo']}"
        if session["codice"]
        else (session["dettaglio"] or "Da assegnare")
    )

    return {
        "risorsa": f"{session['risorsa_nome']} {session['risorsa_cognome']}",
        "risorsa_email": session["risorsa_email"],
        "data": session["data"],
        "data_estesa": long_date(session["data"]),
        "ora_inizio": session["ora_inizio"],
        "ora_fine": session["ora_fine"],
        "modulo": module,
        "dettaglio": session["dettaglio"],
        "note": session["note"],
        "tutor": ", ".join(f"{t['nome']} {t['cognome']}" for t in tutors) or "da assegnare",
        "tutor_righe": [dict(t) for t in tutors],
    }


def _appointment(
    conn: sqlite3.Connection,
    session_id: int,
    context: dict,
    kind: str,
    known_attendees: list[dict],
    organiser: str | None,
) -> str:
    """The calendar invitation, carrying this session's identifier.

    The UID is born with the first notification and never changes: it is what
    lets later messages move or cancel *this* appointment instead of another one
    between the same people. The sequence number rises with every notification,
    or calendars discard the update as a duplicate.
    """
    row = conn.execute(
        "SELECT uid_calendario, revisione_calendario FROM sessione WHERE id = ?",
        (session_id,),
    ).fetchone()

    uid = row["uid_calendario"] or invites.new_uid()
    sequence = row["revisione_calendario"] or 0
    if row["uid_calendario"] is None:
        conn.execute(
            "UPDATE sessione SET uid_calendario = ? WHERE id = ?", (uid, session_id)
        )
    else:
        sequence += 1
        conn.execute(
            "UPDATE sessione SET revisione_calendario = ? WHERE id = ?",
            (sequence, session_id),
        )
    conn.commit()

    description = "\n".join(
        part for part in [
            f"Modulo: {context['modulo']}",
            f"Tutor: {context['tutor']}",
            f"Risorsa in formazione: {context['risorsa']}",
            context.get("note") or "",
        ] if part
    )
    return invites.compose(
        uid=uid,
        sequence=sequence,
        day=context["data"],
        start_time=context["ora_inizio"],
        end_time=context["ora_fine"],
        title=f"Formazione: {context['modulo']}",
        description=description,
        organiser=organiser,
        attendees=known_attendees,
        cancelled=(kind == "annullamento"),
    )


def compose(
    conn: sqlite3.Connection,
    session_id: int,
    kind: str,
    previous: dict | None = None,
    sender_name: str = "Ufficio HR",
    organiser: str | None = None,
) -> dict:
    """Builds subject, body, recipients and invitation. Sends nothing."""
    context = session_context(conn, session_id)
    context["mittente"] = sender_name

    if previous:
        context["data_precedente"] = previous["data"]
        context["data_precedente_estesa"] = long_date(previous["data"])
        context["ora_inizio_precedente"] = previous["ora_inizio"]
        context["ora_fine_precedente"] = previous["ora_fine"]

    subject_template, body_template = _load_template(kind)

    addresses: list[str] = []
    without_email: list[str] = []
    attendees: list[dict] = []
    for tutor in context["tutor_righe"]:
        address = (tutor["email"] or "").strip()
        if address:
            addresses.append(address)
            attendees.append(
                {"nome": f"{tutor['nome']} {tutor['cognome']}", "email": address}
            )
        else:
            without_email.append(f"{tutor['nome']} {tutor['cognome']}")

    trainee_email = (context["risorsa_email"] or "").strip()
    if trainee_email:
        addresses.append(trainee_email)
        attendees.append({"nome": context["risorsa"], "email": trainee_email})
    else:
        without_email.append(context["risorsa"])

    recipients = []
    seen: set[str] = set()
    for address in addresses:
        address = address.strip()
        key = address.casefold()
        if address and key not in seen:
            seen.add(key)
            recipients.append(address)

    return {
        "tipo": kind,
        "sessione_id": session_id,
        "oggetto": subject_template.render(**context),
        "corpo": body_template.render(**context),
        "destinatari": recipients,
        "senza_email": without_email,
        "calendario": _appointment(
            conn, session_id, context, kind, attendees, organiser
        ),
    }


def record(
    conn: sqlite3.Connection,
    message: dict,
    outcome: str,
    error: str | None = None,
    mail_log_id: int | None = None,
) -> None:
    """Logs a notification, or updates the original entry during a retry."""
    recorded_at = datetime.now().isoformat(timespec="seconds")
    sent_at = recorded_at if outcome == "inviata" else None
    values = (
        message["sessione_id"],
        message["tipo"],
        "; ".join(message["destinatari"]),
        message["oggetto"],
        message["corpo"],
        sent_at,
        outcome,
        error,
        json.dumps(message.get("senza_email", []), ensure_ascii=False),
        message.get("calendario"),
    )
    if mail_log_id is None:
        conn.execute(
            """
            INSERT INTO mail_log
                (sessione_id, tipo, destinatari, oggetto, corpo, registrata_il,
                 inviata_il, esito, errore, senza_email, calendario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (values[0], values[1], values[2], values[3], values[4],
             recorded_at, *values[5:]),
        )
    else:
        conn.execute(
            """
            UPDATE mail_log
            SET sessione_id = ?, tipo = ?, destinatari = ?, oggetto = ?, corpo = ?,
                inviata_il = ?, esito = ?, errore = ?, senza_email = ?, calendario = ?
            WHERE id = ?
            """,
            (*values, mail_log_id),
        )
    conn.commit()


def message_from_log(row: Mapping[str, object]) -> dict:
    """Rebuilds the unchanged message a retry sends."""
    recipients = [
        address.strip()
        for address in str(row["destinatari"] or "").split(";")
        if address.strip()
    ]
    try:
        without_email = json.loads(str(row["senza_email"] or "[]"))
    except (TypeError, json.JSONDecodeError):
        without_email = []
    return {
        "tipo": row["tipo"],
        "sessione_id": row["sessione_id"],
        "oggetto": row["oggetto"],
        "corpo": row["corpo"],
        "destinatari": recipients,
        "senza_email": without_email if isinstance(without_email, list) else [],
        # the very same invitation: a retry must not create a new appointment
        "calendario": row["calendario"] if "calendario" in row.keys() else None,
    }


def log_entry(row: sqlite3.Row) -> dict:
    """Turns a log row into a JSON response with its accessory data."""
    entry = dict(row)
    try:
        entry["senza_email"] = json.loads(entry.get("senza_email") or "[]")
    except (TypeError, json.JSONDecodeError):
        entry["senza_email"] = []
    if not isinstance(entry["senza_email"], list):
        entry["senza_email"] = []
    return entry
