"""The local server behind the application.

Response keys that mirror database columns keep their Italian names, for the
same reason the schema does: they are domain identifiers that also travel in the
data. See the glossary in the README.
"""

import asyncio
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, delivery, messages, pdf_export, rules
from .paths import resource_folder

WEB_FOLDER = resource_folder() / "app" / "web"

app = FastAPI(title="Cicerone")
conn: sqlite3.Connection = db.initialise()

# One copy of the archive a day: it is the only copy of the data there is.
db.daily_backup()

# Every area needs a colour: the ones without get theirs here, at start-up.
rules.ensure_area_colours(conn)

# Automatic closing runs at start-up, not at 18:00 sharp, because at that hour
# the computer may well be off.
_closed_at_startup = [dict(s) for s in rules.close_past_sessions(conn)]


class SessionIn(BaseModel):
    piano_id: int
    piano_modulo_id: int | None = None
    data: str
    ora_inizio: str
    ora_fine: str
    dettaglio: str | None = None
    stato: str = "Pianificata"
    note: str | None = None
    tutor: list[int] = []


class SessionPatch(BaseModel):
    piano_modulo_id: int | None = None
    data: str | None = None
    ora_inizio: str | None = None
    ora_fine: str | None = None
    dettaglio: str | None = None
    stato: str | None = None
    esito_verifica: str | None = None
    note: str | None = None
    tutor: list[int] | None = None


class ModulePatch(BaseModel):
    applicabile: str | None = None
    modalita: str | None = None
    tutor_referente_id: int | None = None
    entro_il: str | None = None
    verifica_chiusura: str | None = None
    verifica_efficacia: str | None = None
    data_verifica: str | None = None
    esito: str | None = None


class TraineeIn(BaseModel):
    nome: str
    cognome: str
    email: str | None = None
    reparto: str | None = None
    mansione: str | None = None
    responsabile_id: int | None = None
    tutor_principale_id: int | None = None
    data_inizio: str
    motivo: str = "Nuova funzione"


class CatalogueModuleIn(BaseModel):
    codice: str
    area: str
    titolo: str
    modalita_default: str | None = None
    tutor_referente_default_id: int | None = None
    colore: str | None = None


class AreaIn(BaseModel):
    nome: str
    colore: str


class PersonIn(BaseModel):
    nome: str
    cognome: str
    email: str | None = None
    reparto: str | None = None


class MailSettingIn(BaseModel):
    invio_email_automatico: bool


class MailChannelIn(BaseModel):
    canale: str
    mittente: str | None = None


class FormCodeIn(BaseModel):
    codice: str


class MailTestIn(BaseModel):
    destinatario: str
    canale: str | None = None
    mittente: str | None = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _plan_sessions(plan_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.*, pm.codice, pm.titolo AS modulo_titolo, pm.area,
               a.colore AS colore_area
        FROM sessione s
        LEFT JOIN piano_modulo pm ON pm.id = s.piano_modulo_id
        LEFT JOIN area a ON a.nome = pm.area
        WHERE s.piano_id = ?
        ORDER BY s.data, s.ora_inizio
        """,
        (plan_id,),
    ).fetchall()

    tutors_by_session: dict[int, list[dict]] = {}
    for row in conn.execute(
        """
        SELECT st.sessione_id, p.id, p.nome, p.cognome, p.email
        FROM sessione_tutor st JOIN persona p ON p.id = st.persona_id
        JOIN sessione s ON s.id = st.sessione_id
        WHERE s.piano_id = ?
        """,
        (plan_id,),
    ).fetchall():
        tutors_by_session.setdefault(row["sessione_id"], []).append(
            {"id": row["id"], "nome": f"{row['nome']} {row['cognome']}", "email": row["email"]}
        )

    sessions = []
    for row in rows:
        entry = dict(row)
        entry["tutor"] = tutors_by_session.get(row["id"], [])
        entry["durata"] = rules.duration_hours(row["ora_inizio"], row["ora_fine"])
        entry["colore"] = rules.STATE_COLOURS.get(row["stato"], "#FFFFFF")
        entry["colore_area"] = row["colore_area"] or rules.NEUTRAL_AREA_COLOUR
        sessions.append(entry)
    return sessions


def _set_tutors(session_id: int, tutors: list[int]) -> None:
    conn.execute("DELETE FROM sessione_tutor WHERE sessione_id = ?", (session_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
        [(session_id, t) for t in tutors],
    )


def _upsert_area(name: str, colour: str) -> None:
    """Sets an area's colour, creating the area when it does not exist yet."""
    conn.execute(
        """
        INSERT INTO area (nome, colore, ordine)
        VALUES (?, ?, COALESCE((SELECT MAX(ordine) + 1 FROM area), 0))
        ON CONFLICT(nome) DO UPDATE SET colore = excluded.colore
        """,
        (name, colour),
    )


async def _notify(session_id: int, kind: str, previous: dict | None = None) -> dict:
    message = messages.compose(
        conn, session_id, kind, previous=previous,
        # the appointment's organiser is the address chosen during setup
        organiser=db.read_setting(conn, db.KEY_MAIL_SENDER),
    )
    outcome = await delivery.send_without_blocking(conn, message)
    return {"oggetto": message["oggetto"], **outcome}


@app.get("/api/state")
async def state():
    plans = conn.execute(
        """
        SELECT p.id, p.creato_il, r.reparto, r.mansione, r.data_inizio,
               pe.nome || ' ' || pe.cognome AS risorsa
        FROM piano p JOIN risorsa r ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        ORDER BY r.data_inizio DESC
        """
    ).fetchall()
    without_email = conn.execute(
        "SELECT COUNT(*) c FROM persona WHERE email IS NULL OR email = ''"
    ).fetchone()["c"]
    return {
        "plans": [dict(p) for p in plans],
        "closed_at_startup": _closed_at_startup,
        "people_without_email": without_email,
        "mail_channel": delivery.choose_channel(conn).name,
        "automatic_email": db.automatic_email_delivery(conn),
        # While this is false the app does not know where to send from: the
        # interface asks.
        "mail_configured": bool(db.read_setting(conn, db.KEY_MAIL_CHANNEL)),
        "mail_sender": db.read_setting(conn, db.KEY_MAIL_SENDER),
        "form_code": db.read_setting(
            conn, db.KEY_FORM_CODE, db.DEFAULT_FORM_CODE
        ),
    }


@app.get("/api/plan/{plan_id}")
async def plan(plan_id: int):
    header = conn.execute(
        """
        SELECT p.id, r.reparto, r.mansione, r.data_inizio, r.motivo,
               pe.nome || ' ' || pe.cognome AS risorsa,
               resp.nome || ' ' || resp.cognome AS responsabile,
               tut.nome  || ' ' || tut.cognome  AS tutor_principale
        FROM piano p JOIN risorsa r ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        LEFT JOIN persona resp ON resp.id = r.responsabile_id
        LEFT JOIN persona tut  ON tut.id  = r.tutor_principale_id
        WHERE p.id = ?
        """,
        (plan_id,),
    ).fetchone()
    if header is None:
        raise HTTPException(404, "piano inesistente")

    area_colours = {
        r["nome"]: r["colore"] for r in conn.execute("SELECT nome, colore FROM area")
    }
    modules = rules.module_summary(conn, plan_id)
    for module in modules:
        module["colore"] = rules.STATE_COLOURS.get(module["stato"], "#FFFFFF")
        module["colore_area"] = area_colours.get(module["area"], rules.NEUTRAL_AREA_COLOUR)
    return {
        "header": dict(header),
        "modules": modules,
        "sessions": _plan_sessions(plan_id),
    }


@app.post("/api/trainees")
async def create_trainee(data: TraineeIn):
    """Creates the person, the trainee and their plan, copying the catalogue.

    It is the only way to start a path without going through a spreadsheet and
    Python, neither of which exist on the computer where the program runs.
    """
    now = _now()
    person = conn.execute(
        "SELECT id FROM persona WHERE nome = ? AND cognome = ?",
        (data.nome, data.cognome),
    ).fetchone()
    if person:
        person_id = person["id"]
        if data.email:
            conn.execute("UPDATE persona SET email = ? WHERE id = ?", (data.email, person_id))
    else:
        person_id = conn.execute(
            "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)",
            (data.nome, data.cognome, data.email, data.reparto),
        ).lastrowid

    trainee_id = conn.execute(
        """
        INSERT INTO risorsa (persona_id, reparto, mansione, responsabile_id,
                             tutor_principale_id, data_inizio, motivo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (person_id, data.reparto, data.mansione, data.responsabile_id,
         data.tutor_principale_id, data.data_inizio, data.motivo),
    ).lastrowid

    plan_id = conn.execute(
        "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, ?)", (trainee_id, now)
    ).lastrowid

    catalogue = conn.execute("SELECT * FROM modulo_catalogo ORDER BY ordine").fetchall()
    for module in catalogue:
        conn.execute(
            """
            INSERT INTO piano_modulo
                (piano_id, codice, area, titolo, applicabile, modalita,
                 tutor_referente_id, ordine)
            VALUES (?, ?, ?, ?, 'SI', ?, ?, ?)
            """,
            (plan_id, module["codice"], module["area"], module["titolo"],
             module["modalita_default"], module["tutor_referente_default_id"],
             module["ordine"]),
        )
    conn.commit()
    return {"plan_id": plan_id, "trainee_id": trainee_id, "modules": len(catalogue)}


@app.get("/api/catalogue")
async def catalogue():
    rows = conn.execute(
        """
        SELECT c.*, p.nome || ' ' || p.cognome AS tutor,
               a.colore AS colore,
               (SELECT COUNT(*) FROM piano_modulo pm WHERE pm.codice = c.codice) AS usato_in
        FROM modulo_catalogo c
        LEFT JOIN persona p ON p.id = c.tutor_referente_default_id
        LEFT JOIN area a ON a.nome = c.area
        ORDER BY c.ordine
        """
    ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/catalogue")
async def create_catalogue_module(data: CatalogueModuleIn):
    existing = conn.execute(
        "SELECT 1 FROM modulo_catalogo WHERE codice = ?", (data.codice,)
    ).fetchone()
    if existing:
        raise HTTPException(400, f"il codice {data.codice} esiste gia'")
    order = conn.execute(
        "SELECT COALESCE(MAX(ordine), 0) + 1 AS o FROM modulo_catalogo"
    ).fetchone()["o"]
    conn.execute(
        """
        INSERT INTO modulo_catalogo
            (codice, area, titolo, modalita_default, tutor_referente_default_id, ordine)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (data.codice, data.area, data.titolo, data.modalita_default,
         data.tutor_referente_default_id, order),
    )
    if data.colore:
        _upsert_area(data.area, data.colore)
    else:
        rules.ensure_area_colours(conn)  # new area with no colour: use a default
    conn.commit()
    return {"codice": data.codice}


@app.patch("/api/catalogue/{code}")
async def update_catalogue_module(code: str, data: CatalogueModuleIn):
    conn.execute(
        """
        UPDATE modulo_catalogo
        SET area = ?, titolo = ?, modalita_default = ?, tutor_referente_default_id = ?
        WHERE codice = ?
        """,
        (data.area, data.titolo, data.modalita_default,
         data.tutor_referente_default_id, code),
    )
    if data.colore:
        _upsert_area(data.area, data.colore)
    else:
        rules.ensure_area_colours(conn)
    conn.commit()
    return {"codice": code}


@app.delete("/api/catalogue/{code}")
async def delete_catalogue_module(code: str):
    """Removes a module from the catalogue. Existing plans do not change."""
    conn.execute("DELETE FROM modulo_catalogo WHERE codice = ?", (code,))
    conn.commit()
    return {"codice": code}


@app.get("/api/areas")
async def areas():
    """Training areas with their colour, for the legend and the editor."""
    rows = conn.execute(
        "SELECT nome, colore, ordine FROM area ORDER BY ordine, nome"
    ).fetchall()
    return [dict(r) for r in rows]


@app.put("/api/areas")
async def save_area(data: AreaIn):
    """Changes an area's colour: it applies to every module in it."""
    _upsert_area(data.nome, data.colore)
    conn.commit()
    return {"nome": data.nome, "colore": data.colore}


@app.put("/api/form-code")
async def save_form_code(data: FormCodeIn):
    """The form code printed at the top of the PDF.

    Every company has its own, taken from its quality system: it lives in the
    archive, not in the code.
    """
    db.save_setting(conn, db.KEY_FORM_CODE, data.codice.strip())
    return {"codice": data.codice.strip()}


@app.post("/api/plan/{plan_id}/print")
async def print_plan(plan_id: int):
    """Generates the PDF form and opens it with the system viewer."""
    path = pdf_export.generate(conn, plan_id)
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass  # the file is saved anyway, and its path is in the response
    return {"percorso": str(path)}


@app.get("/api/clashes")
async def clashes(
    piano_id: int, data: str, ora_inizio: str, ora_fine: str,
    tutor: str = "", escludi: int | None = None,
):
    """Sessions that overlap with the one being proposed."""
    tutor_ids = [int(t) for t in tutor.split(",") if t.strip()]
    return rules.overlaps(
        conn, piano_id, data, ora_inizio, ora_fine, tutor_ids, escludi
    )


@app.post("/api/sessions")
async def create_session(data: SessionIn):
    now = _now()
    session_id = conn.execute(
        """
        INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio, ora_fine,
                              dettaglio, stato, note, creata_il, modificata_il)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (data.piano_id, data.piano_modulo_id, data.data, data.ora_inizio, data.ora_fine,
         data.dettaglio, data.stato, data.note, now, now),
    ).lastrowid
    _set_tutors(session_id, data.tutor)
    conn.commit()
    return {"id": session_id, "mail": await _notify(session_id, "nuova")}


@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: int, data: SessionPatch):
    before = conn.execute("SELECT * FROM sessione WHERE id = ?", (session_id,)).fetchone()
    if before is None:
        raise HTTPException(404, "sessione inesistente")

    fields = data.model_dump(exclude_none=True)
    tutors = fields.pop("tutor", None)

    if fields:
        assignments = ", ".join(f"{c} = ?" for c in fields)
        conn.execute(
            f"UPDATE sessione SET {assignments}, modificata_il = ? WHERE id = ?",
            (*fields.values(), _now(), session_id),
        )
    if tutors is not None:
        _set_tutors(session_id, tutors)
    conn.commit()

    # An explicit edit leaves the automatic regime.
    if fields.get("stato") or fields.get("esito_verifica"):
        conn.execute(
            "UPDATE sessione SET chiusa_automaticamente = 0 WHERE id = ?", (session_id,)
        )
        conn.commit()

    moved = any(
        fields.get(c) is not None and fields[c] != before[c]
        for c in ("data", "ora_inizio", "ora_fine")
    )
    response = {"id": session_id, "spostata": moved}
    if moved:
        response["mail"] = await _notify(
            session_id,
            "spostamento",
            previous={
                "data": before["data"],
                "ora_inizio": before["ora_inizio"],
                "ora_fine": before["ora_fine"],
            },
        )
    elif fields.get("stato") == "Annullata":
        response["mail"] = await _notify(session_id, "annullamento")
    return response


@app.delete("/api/sessions/{session_id}")
async def cancel_session(session_id: int):
    """Sessions are never deleted: they are cancelled, and stay in the plan."""
    conn.execute(
        "UPDATE sessione SET stato = 'Annullata', modificata_il = ? WHERE id = ?",
        (_now(), session_id),
    )
    conn.commit()
    return {"id": session_id, "mail": await _notify(session_id, "annullamento")}


@app.patch("/api/modules/{module_id}")
async def update_module(module_id: int, data: ModulePatch):
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return {"id": module_id}
    assignments = ", ".join(f"{c} = ?" for c in fields)
    conn.execute(
        f"UPDATE piano_modulo SET {assignments} WHERE id = ?", (*fields.values(), module_id)
    )
    conn.commit()
    return {"id": module_id}


@app.get("/api/people")
async def people():
    rows = conn.execute(
        """
        SELECT p.*, EXISTS (SELECT 1 FROM risorsa r WHERE r.persona_id = p.id) AS e_risorsa
        FROM persona p WHERE p.attivo = 1 ORDER BY p.cognome, p.nome
        """
    ).fetchall()
    return [dict(r) for r in rows]


@app.patch("/api/people/{person_id}")
async def update_person(person_id: int, data: PersonIn):
    conn.execute(
        "UPDATE persona SET nome = ?, cognome = ?, email = ?, reparto = ? WHERE id = ?",
        (data.nome, data.cognome, data.email, data.reparto, person_id),
    )
    conn.commit()
    return {"id": person_id}


@app.post("/api/people")
async def create_person(data: PersonIn):
    cursor = conn.execute(
        "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)",
        (data.nome, data.cognome, data.email, data.reparto),
    )
    conn.commit()
    return {"id": cursor.lastrowid}


@app.get("/api/mail")
async def mail_log():
    rows = conn.execute(
        """
        SELECT m.*, s.data AS sessione_data
        FROM mail_log m LEFT JOIN sessione s ON s.id = m.sessione_id
        ORDER BY m.id DESC LIMIT 200
        """
    ).fetchall()
    return [messages.log_entry(r) for r in rows]


@app.get("/api/mail/settings")
async def mail_settings():
    """The stored state of automatic delivery."""
    return {"invio_email_automatico": db.automatic_email_delivery(conn)}


@app.put("/api/mail/settings")
async def save_mail_settings(data: MailSettingIn):
    """Turns real delivery of the notifications on or off."""
    db.save_setting(
        conn,
        db.KEY_AUTO_EMAIL,
        "1" if data.invio_email_automatico else "0",
    )
    return {"invio_email_automatico": data.invio_email_automatico}


@app.get("/api/mail/channels")
async def mail_channels():
    """The mail programs on this computer, with their accounts.

    It really asks the programs, so it may launch them: acceptable here,
    because it is called from the setup screen and not on every page load.
    """
    found = await asyncio.to_thread(delivery.available_channels)
    return {
        "canali": found,
        "scelto": db.read_setting(conn, db.KEY_MAIL_CHANNEL),
        "mittente": db.read_setting(conn, db.KEY_MAIL_SENDER),
    }


@app.put("/api/mail/channel")
async def save_mail_channel(data: MailChannelIn):
    """Records where the notifications will be sent from on this computer."""
    if delivery.channel_by_name(data.canale) is None:
        raise HTTPException(400, f"canale sconosciuto: {data.canale}")
    db.save_setting(conn, db.KEY_MAIL_CHANNEL, data.canale)
    db.save_setting(conn, db.KEY_MAIL_SENDER, data.mittente or "")
    return {"canale": data.canale, "mittente": data.mittente or ""}


@app.post("/api/mail/test")
async def test_mail(data: MailTestIn):
    """Sends a test message and reports what actually happened.

    It does not go through the automatic-delivery policy: its whole point is to
    check that the channel works *before* turning that on. It does not enter the
    notification log, which documents training and not technical tests.

    It runs in a thread because it waits for the mail program to take the
    message out of the outbox: on the event loop that would block the whole app.
    """
    if data.canale:
        channel = delivery.channel_by_name(data.canale, data.mittente)
        if channel is None:
            raise HTTPException(400, f"canale sconosciuto: {data.canale}")
    else:
        channel = delivery.choose_channel(conn)

    message = {
        "tipo": "prova",
        "sessione_id": 0,
        "oggetto": "Cicerone: prova di invio",
        "corpo": (
            "Questa e' una prova dell'invio automatico di Cicerone.\n\n"
            "Se la stai leggendo, le notifiche di creazione, spostamento e "
            "annullamento delle sessioni possono partire da questo computer.\n"
        ),
        "destinatari": [data.destinatario.strip()],
        "senza_email": [],
    }
    try:
        await asyncio.to_thread(channel.send, message)
    except Exception as error:
        return {"esito": "errore", "canale": channel.name, "errore": str(error)}
    return {"esito": "inviata", "canale": channel.name}


@app.post("/api/mail/retry-all")
async def retry_all_mail():
    """Retries the blocked or failed notifications, oldest first.

    Useful after switching delivery on or fixing the mail program: everything
    left behind goes out without picking the entries up one by one.
    """
    rows = conn.execute(
        """
        SELECT * FROM mail_log
        WHERE esito IN ('invio_disattivato', 'errore')
        ORDER BY id
        """
    ).fetchall()

    summary = {"totale": len(rows), "inviate": 0, "errori": 0, "bloccate": 0}
    for row in rows:
        outcome = await delivery.send_without_blocking(
            conn, messages.message_from_log(row), mail_log_id=row["id"]
        )
        if outcome["esito"] == "inviata":
            summary["inviate"] += 1
        elif outcome["esito"] == "errore":
            summary["errori"] += 1
        else:
            summary["bloccate"] += 1
    return summary


@app.post("/api/mail/{mail_id}/retry")
async def retry_mail(mail_id: int):
    """Retries one delivery without creating a new log entry."""
    row = conn.execute(
        "SELECT * FROM mail_log WHERE id = ?", (mail_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "voce del registro inesistente")
    if row["esito"] not in {"invio_disattivato", "errore"}:
        raise HTTPException(409, "questa mail non e' riprovabile")
    message = messages.message_from_log(row)
    return {
        "id": mail_id,
        **await delivery.send_without_blocking(conn, message, mail_log_id=mail_id),
    }


@app.delete("/api/mail/{mail_id}")
async def delete_mail(mail_id: int):
    """Deletes one entry from the delivery log, and nothing else."""
    cursor = conn.execute("DELETE FROM mail_log WHERE id = ?", (mail_id,))
    if cursor.rowcount == 0:
        raise HTTPException(404, "voce del registro inesistente")
    conn.commit()
    return {"id": mail_id}


@app.middleware("http")
async def no_cache(request, call_next):
    """The interface must never be cached.

    Server and page are updated together: an old JavaScript left in the cache
    against a new HTML produces errors that look like bugs in the app.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
async def home():
    return FileResponse(WEB_FOLDER / "index.html")


app.mount("/static", StaticFiles(directory=WEB_FOLDER), name="static")
