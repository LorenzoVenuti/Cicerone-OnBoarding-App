"""Plan calculation and automatic closing of past sessions.

One direction only: sessions are the facts, everything else is derived.
Replaces the COUNTIFS/MINIFS/SUMIFS formulas of the original spreadsheet.

Domain values (session states such as `Svolta` or `Pianificata`, and the column
names) stay in Italian: they are stored in the database and appear in the data,
so translating them here would leave code and archives disagreeing. See the
glossary in the README.
"""

import sqlite3
from datetime import date, datetime, time

AUTO_CLOSE_TIME = time(18, 0)

# States that do not count as a planned session (these were the "<>Annullata"
# and "<>Rinviata" of the spreadsheet formulas).
EXCLUDED_STATES = ("Annullata", "Rinviata")
OPEN_STATES = ("Pianificata", "Confermata")

STATE_COLOURS = {
    "Svolta": "#C6EFCE",
    "Completata": "#C6EFCE",
    "In corso": "#BDD7EE",
    "Rinviata": "#FCE4D6",
    "Da pianificare": "#FCE4D6",
    "Annullata": "#F2DCDB",
    "N.A.": "#D9D9D9",
    "Pianificata": "#FFFFFF",
    "Confermata": "#FFFFFF",
}

# Neutral colour for a session with no module, or an area with no colour.
NEUTRAL_AREA_COLOUR = "#E9ECF0"

# Twelve clearly distinct pastel shades (a full turn of the colour wheel): they
# fill the calendar blocks and the agenda border, always under dark text, so
# they stay readable in dark mode too. They are only a starting point: the user
# can change the colour of every area.
AREA_PALETTE = [
    "#F5C9C9", "#F5DCC0", "#F0EEBE", "#DBEEBE", "#C6EFCE", "#C0EFD6",
    "#BEEFEF", "#C0DCF5", "#C9C9F5", "#DCC0F5", "#F0BEEF", "#F5C0DC",
]


def ensure_area_colours(conn: sqlite3.Connection) -> None:
    """Make sure every area has a colour. Idempotent.

    Areas start life as plain strings on the modules; here the ones that do not
    have a colour yet are given a default, cycling through the palette. Call it
    at start-up: that way an existing archive, created before areas had colours,
    fills itself in without a hand-written migration.
    """
    known = {r["nome"] for r in conn.execute("SELECT nome FROM area")}

    areas: list[str] = []
    for row in conn.execute(
        "SELECT area, MIN(ordine) AS o FROM modulo_catalogo GROUP BY area ORDER BY o"
    ):
        areas.append(row["area"])
    for row in conn.execute("SELECT DISTINCT area FROM piano_modulo"):
        if row["area"] not in areas:
            areas.append(row["area"])

    missing = [a for a in areas if a not in known]
    if not missing:
        return
    base = len(known)
    conn.executemany(
        "INSERT OR IGNORE INTO area (nome, colore, ordine) VALUES (?, ?, ?)",
        [
            (area, AREA_PALETTE[(base + i) % len(AREA_PALETTE)], base + i)
            for i, area in enumerate(missing)
        ],
    )
    conn.commit()


def add_module_to_open_plans(conn: sqlite3.Connection, code: str) -> int:
    """Gives a newly catalogued module to the plans that are still open.

    A plan is a copy of the catalogue taken the day the plan was created, not a
    live view of it, and that is deliberate: a closed plan is a certification
    document and must not change under the person who signed it.

    But the copy left a hole. Whoever fills the catalogue after creating the
    first trainee - which is the natural order when starting from an empty
    archive - ended up with a plan that had no modules at all, and no way to
    schedule anything for that person. So a module added to the catalogue
    reaches every plan that is still open, and no closed one.

    Returns how many plans gained it. Idempotent, thanks to the UNIQUE on
    (piano_id, codice): a plan that already has the code is left alone.
    """
    module = conn.execute(
        "SELECT * FROM modulo_catalogo WHERE codice = ?", (code,)
    ).fetchone()
    if module is None:
        return 0

    added = 0
    for plan in conn.execute("SELECT id FROM piano WHERE chiuso_il IS NULL").fetchall():
        # At the end of that plan's list: the catalogue's own order says nothing
        # about where it belongs in a plan that was built before it existed.
        order = conn.execute(
            "SELECT COALESCE(MAX(ordine), 0) + 1 AS o FROM piano_modulo WHERE piano_id = ?",
            (plan["id"],),
        ).fetchone()["o"]
        added += conn.execute(
            """
            INSERT OR IGNORE INTO piano_modulo
                (piano_id, codice, area, titolo, applicabile, modalita,
                 tutor_referente_id, ordine)
            VALUES (?, ?, ?, ?, 'SI', ?, ?, ?)
            """,
            (plan["id"], module["codice"], module["area"], module["titolo"],
             module["modalita_default"], module["tutor_referente_default_id"], order),
        ).rowcount
    conn.commit()
    return added


def align_open_plans_with_catalogue(conn: sqlite3.Connection) -> dict[str, int]:
    """Brings every open plan back in line with the catalogue. Idempotent.

    Two things drift apart, and both were reported from real use:

    - a module catalogued *before* this existed never reached the plans already
      created, and there is no way to add it from the interface, so it stayed
      out of reach for good;
    - renaming a module in the catalogue left the plans showing the old title,
      because the plan holds a copy.

    Only `titolo` and `area` are realigned, and that is not an arbitrary choice:
    they are the only columns of `piano_modulo` the interface does **not** let
    you edit per plan. `applicabile`, `modalita` and `tutor_referente_id` are
    per-plan decisions, and overwriting them from the catalogue would silently
    throw away somebody's work. The form's verification columns are untouched
    for the same reason.

    Closed plans are never touched: they are signed documents.

    Runs at start-up like `ensure_area_colours`, so an archive that predates
    this repairs itself without a hand-written migration.
    """
    added = 0
    for row in conn.execute("SELECT codice FROM modulo_catalogo ORDER BY ordine"):
        added += add_module_to_open_plans(conn, row["codice"])

    updated = conn.execute(
        """
        UPDATE piano_modulo
        SET titolo = (SELECT c.titolo FROM modulo_catalogo c
                      WHERE c.codice = piano_modulo.codice),
            area   = (SELECT c.area   FROM modulo_catalogo c
                      WHERE c.codice = piano_modulo.codice)
        WHERE piano_id IN (SELECT id FROM piano WHERE chiuso_il IS NULL)
          AND EXISTS (SELECT 1 FROM modulo_catalogo c
                      WHERE c.codice = piano_modulo.codice
                        AND (c.titolo IS NOT piano_modulo.titolo
                             OR c.area IS NOT piano_modulo.area))
        """
    ).rowcount
    conn.commit()
    return {"added": added, "updated": updated}


def plan_is_closed(conn: sqlite3.Connection, plan_id: int) -> bool:
    """Whether that plan has been declared finished."""
    row = conn.execute(
        "SELECT chiuso_il FROM piano WHERE id = ?", (plan_id,)
    ).fetchone()
    return bool(row and row["chiuso_il"])


def close_plan(conn: sqlite3.Connection, plan_id: int, when: str) -> str | None:
    """Declares a plan finished, and stops it changing on its own.

    From here on the plan no longer follows the catalogue, automatic completion
    leaves its sessions alone, and the API refuses to write to it. That is the
    point: the training plan is a certification record, and once it is signed it
    has to keep saying what it said.

    Closing twice keeps the first date: it is when the plan was declared over,
    not when somebody last pressed the button.
    """
    already = conn.execute(
        "SELECT chiuso_il FROM piano WHERE id = ?", (plan_id,)
    ).fetchone()
    if already is None:
        return None
    if already["chiuso_il"]:
        return already["chiuso_il"]
    conn.execute("UPDATE piano SET chiuso_il = ? WHERE id = ?", (when, plan_id))
    conn.commit()
    return when


def reopen_plan(conn: sqlite3.Connection, plan_id: int) -> None:
    """Undoes a closing.

    It exists because the closing is one click and people misclick. Without a
    way back, a mistake would be permanent from the interface, and the only
    remedy would be somebody editing the database by hand.
    """
    conn.execute("UPDATE piano SET chiuso_il = NULL WHERE id = ?", (plan_id,))
    conn.commit()


def duration_hours(start_time: str, end_time: str) -> float:
    """Length in hours between two 'HH:MM' times."""
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    return (end - start).total_seconds() / 3600


def module_state(applicable: str, planned: int, done: int) -> str:
    if applicable == "NO":
        return "N.A."
    if planned == 0:
        return "Da pianificare"
    if done >= planned:
        return "Completata"
    if done > 0:
        return "In corso"
    return "Pianificata"


def module_summary(conn: sqlite3.Connection, plan_id: int) -> list[dict]:
    """The training plan, computed: one row per module."""
    modules = conn.execute(
        """
        SELECT pm.*, p.nome AS tutor_nome, p.cognome AS tutor_cognome
        FROM piano_modulo pm
        LEFT JOIN persona p ON p.id = pm.tutor_referente_id
        WHERE pm.piano_id = ?
        ORDER BY pm.ordine
        """,
        (plan_id,),
    ).fetchall()

    rows = []
    for module in modules:
        sessions = conn.execute(
            "SELECT data, ora_inizio, ora_fine, stato FROM sessione WHERE piano_modulo_id = ?",
            (module["id"],),
        ).fetchall()

        valid = [s for s in sessions if s["stato"] not in EXCLUDED_STATES]
        done = [s for s in valid if s["stato"] == "Svolta"]
        valid_dates = sorted(s["data"] for s in valid)

        rows.append(
            {
                "id": module["id"],
                "codice": module["codice"],
                "area": module["area"],
                "titolo": module["titolo"],
                "applicabile": module["applicabile"],
                "modalita": module["modalita"],
                "tutor_referente_id": module["tutor_referente_id"],
                "tutor_referente": (
                    f"{module['tutor_nome']} {module['tutor_cognome']}"
                    if module["tutor_nome"]
                    else None
                ),
                "dal": valid_dates[0] if valid_dates else None,
                "al": valid_dates[-1] if valid_dates else None,
                "sessioni_pianificate": len(valid),
                "sessioni_svolte": len(done),
                "ore_svolte": round(
                    sum(duration_hours(s["ora_inizio"], s["ora_fine"]) for s in done), 2
                ),
                "stato": module_state(module["applicabile"], len(valid), len(done)),
                "entro_il": module["entro_il"],
                "verifica_chiusura": module["verifica_chiusura"],
                "verifica_efficacia": module["verifica_efficacia"],
                "data_verifica": module["data_verifica"],
                "esito": module["esito"],
            }
        )
    return rows


def sessions_to_close(
    conn: sqlite3.Connection, now: datetime | None = None
) -> list[sqlite3.Row]:
    """Past sessions left open, which auto-completion should close.

    A session should be closed if it is still open, it is in the past, and
    nobody has rescheduled it: if a newer session replaces it, the old one was
    postponed by hand and is none of our business.
    """
    now = now or datetime.now()
    today = now.date().isoformat()

    # A closed plan is a signed document: automatic completion would be marking
    # sessions Svolta inside it, months after somebody declared it finished.
    candidates = conn.execute(
        f"""
        SELECT s.* FROM sessione s
        JOIN piano p ON p.id = s.piano_id
        WHERE s.stato IN ({",".join("?" * len(OPEN_STATES))})
          AND s.data <= ?
          AND p.chiuso_il IS NULL
        ORDER BY s.data, s.ora_inizio
        """,
        (*OPEN_STATES, today),
    ).fetchall()

    to_close = []
    for session in candidates:
        if session["data"] == today and now.time() < AUTO_CLOSE_TIME:
            continue  # the day is not over yet
        replaced = conn.execute(
            "SELECT 1 FROM sessione WHERE sostituisce_id = ? LIMIT 1", (session["id"],)
        ).fetchone()
        if replaced:
            continue
        to_close.append(session)
    return to_close


def close_past_sessions(
    conn: sqlite3.Connection, now: datetime | None = None
) -> list[sqlite3.Row]:
    """Mark past sessions left open as done, with outcome OK.

    Runs when the app starts, not at 18:00 sharp: the computer may well be off
    at that hour. Closed sessions stay flagged as closed automatically.
    """
    now = now or datetime.now()
    closed = sessions_to_close(conn, now)
    if not closed:
        return []

    conn.executemany(
        """
        UPDATE sessione
        SET stato = 'Svolta',
            esito_verifica = COALESCE(NULLIF(esito_verifica, ''), 'OK'),
            chiusa_automaticamente = 1,
            modificata_il = ?
        WHERE id = ?
        """,
        [(now.isoformat(timespec="seconds"), s["id"]) for s in closed],
    )
    conn.commit()
    return closed


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def overlaps(
    conn: sqlite3.Connection,
    plan_id: int,
    day: str,
    start_time: str,
    end_time: str,
    tutors: list[int] | None = None,
    ignore_session: int | None = None,
) -> list[dict]:
    """Sessions that clash with the one being proposed.

    Two cases genuinely prevent an appointment: the trainee cannot be in two
    places at once, and neither can a tutor — who may however be busy on
    somebody else's plan. Cancelled and postponed sessions do not count.
    """
    start, end = _minutes(start_time), _minutes(end_time)
    tutors = tutors or []

    candidates = conn.execute(
        f"""
        SELECT s.*, pe.nome || ' ' || pe.cognome AS risorsa
        FROM sessione s
        JOIN piano p    ON p.id = s.piano_id
        JOIN risorsa r  ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        WHERE s.data = ?
          AND s.stato NOT IN ({",".join("?" * len(EXCLUDED_STATES))})
          AND (? IS NULL OR s.id != ?)
        """,
        (day, *EXCLUDED_STATES, ignore_session, ignore_session),
    ).fetchall()

    clashes = []
    for other in candidates:
        if _minutes(other["ora_inizio"]) >= end or _minutes(other["ora_fine"]) <= start:
            continue

        if other["piano_id"] == plan_id:
            reason, who = "risorsa", other["risorsa"]
        else:
            other_tutors = {
                r["persona_id"]
                for r in conn.execute(
                    "SELECT persona_id FROM sessione_tutor WHERE sessione_id = ?",
                    (other["id"],),
                ).fetchall()
            }
            shared = other_tutors & set(tutors)
            if not shared:
                continue
            names = conn.execute(
                f"""SELECT nome || ' ' || cognome AS n FROM persona
                    WHERE id IN ({",".join("?" * len(shared))})""",
                tuple(shared),
            ).fetchall()
            reason, who = "tutor", ", ".join(r["n"] for r in names)

        clashes.append(
            {
                "sessione_id": other["id"],
                "motivo": reason,
                "chi": who,
                "data": other["data"],
                "ora_inizio": other["ora_inizio"],
                "ora_fine": other["ora_fine"],
                "dettaglio": other["dettaglio"],
                "risorsa": other["risorsa"],
            }
        )
    return clashes
