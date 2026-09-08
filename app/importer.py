"""One-off import of the data from the original spreadsheet.

The spreadsheet is only the starting point: after this import the app stands on
its own and the file is never read or written again.
"""

import sqlite3
from datetime import date, datetime, time
from pathlib import Path

import openpyxl

from . import db


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date(value) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _time(value) -> str | None:
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return None


def _split_name(whole: str) -> tuple[str, str]:
    """'Maria Rossi Bianchi' -> ('Maria', 'Rossi Bianchi')."""
    parti = whole.strip().split(None, 1)
    return (parti[0], parti[1]) if len(parti) == 2 else (whole.strip(), "")


def find_person(conn: sqlite3.Connection, full_name: str) -> int:
    """Returns the person's id, creating the record when missing."""
    nome, cognome = _split_name(full_name)
    row = conn.execute(
        "SELECT id FROM persona WHERE nome = ? AND cognome = ?", (nome, cognome)
    ).fetchone()
    if row:
        return row["id"]
    cursore = conn.execute(
        "INSERT INTO persona (nome, cognome) VALUES (?, ?)", (nome, cognome)
    )
    return cursore.lastrowid


def import_spreadsheet(spreadsheet_path: Path | str, conn: sqlite3.Connection) -> dict:
    wb = openpyxl.load_workbook(spreadsheet_path, data_only=True)
    adesso = datetime.now().isoformat(timespec="seconds")

    # --- anagrafica tutor (sheet Dati, colonna F) ---
    dati = wb["Dati"]
    for row in range(2, dati.max_row + 1):
        nome = _text(dati.cell(row, 6).value)
        if nome:
            find_person(conn, nome)

    # --- the plan's header (sheet Piano ISO) ---
    piano_iso = wb["Piano ISO"]
    nome_risorsa = _text(piano_iso["C4"].value)
    reparto = _text(piano_iso["H4"].value)
    mansione = _text(piano_iso["M4"].value)
    responsabile = _text(piano_iso["C5"].value)
    tutor_principale = _text(piano_iso["H5"].value)
    data_inizio = _date(piano_iso["M5"].value)

    persona_risorsa = find_person(conn, nome_risorsa)
    risorsa_id = conn.execute(
        """
        INSERT INTO risorsa
            (persona_id, reparto, mansione, responsabile_id, tutor_principale_id,
             data_inizio, motivo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            persona_risorsa,
            reparto,
            mansione,
            find_person(conn, responsabile) if responsabile else None,
            find_person(conn, tutor_principale) if tutor_principale else None,
            data_inizio,
            "Formazione",
        ),
    ).lastrowid

    piano_id = conn.execute(
        "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, ?)", (risorsa_id, adesso)
    ).lastrowid

    # --- modules: rows 9..29 of the Piano ISO sheet ---
    moduli_per_codice: dict[str, int] = {}
    ordine = 0
    for row in range(9, 30):
        codice = _text(piano_iso.cell(row, 1).value)
        if not codice:
            continue
        ordine += 1
        area = _text(piano_iso.cell(row, 2).value) or ""
        titolo = _text(piano_iso.cell(row, 3).value) or ""
        applicabile = _text(piano_iso.cell(row, 4).value) or "SI"
        modalita = _text(piano_iso.cell(row, 5).value)
        tutor = _text(piano_iso.cell(row, 6).value)
        tutor_id = find_person(conn, tutor) if tutor else None

        conn.execute(
            """
            INSERT INTO modulo_catalogo
                (codice, area, titolo, modalita_default, tutor_referente_default_id, ordine)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(codice) DO NOTHING
            """,
            (codice, area, titolo, modalita, tutor_id, ordine),
        )
        moduli_per_codice[codice] = conn.execute(
            """
            INSERT INTO piano_modulo
                (piano_id, codice, area, titolo, applicabile, modalita,
                 tutor_referente_id, ordine, entro_il, verifica_chiusura,
                 verifica_efficacia, data_verifica, esito)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                piano_id, codice, area, titolo, applicabile, modalita, tutor_id, ordine,
                _date(piano_iso.cell(row, 13).value),
                _text(piano_iso.cell(row, 14).value),
                _text(piano_iso.cell(row, 15).value),
                _date(piano_iso.cell(row, 16).value),
                _text(piano_iso.cell(row, 17).value),
            ),
        ).lastrowid

    # --- sessioni ---
    sessioni_foglio = wb["Sessioni"]
    n_sessioni = 0
    senza_modulo = []
    for row in range(2, sessioni_foglio.max_row + 1):
        data_sessione = _date(sessioni_foglio.cell(row, 1).value)
        if not data_sessione:
            continue
        ora_inizio = _time(sessioni_foglio.cell(row, 3).value)
        ora_fine = _time(sessioni_foglio.cell(row, 4).value)
        if not ora_inizio or not ora_fine:
            continue

        codice = _text(sessioni_foglio.cell(row, 6).value)
        dettaglio = _text(sessioni_foglio.cell(row, 8).value)
        tutor_cella = _text(sessioni_foglio.cell(row, 9).value)
        stato = _text(sessioni_foglio.cell(row, 10).value) or "Pianificata"
        esito = _text(sessioni_foglio.cell(row, 11).value)
        note = _text(sessioni_foglio.cell(row, 12).value)

        modulo_id = moduli_per_codice.get(codice) if codice else None
        if modulo_id is None:
            senza_modulo.append(f"{data_sessione} {dettaglio or ''}".strip())

        sessione_id = conn.execute(
            """
            INSERT INTO sessione
                (piano_id, piano_modulo_id, data, ora_inizio, ora_fine, dettaglio,
                 stato, esito_verifica, note, creata_il, modificata_il)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                piano_id, modulo_id, data_sessione, ora_inizio, ora_fine, dettaglio,
                stato, esito.upper() if esito else None, note, adesso, adesso,
            ),
        ).lastrowid
        n_sessioni += 1

        for nome_tutor in (tutor_cella or "").split(","):
            nome_tutor = nome_tutor.strip()
            if nome_tutor:
                conn.execute(
                    "INSERT OR IGNORE INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
                    (sessione_id, find_person(conn, nome_tutor)),
                )

    conn.commit()
    return {
        "piano_id": piano_id,
        "risorsa": nome_risorsa,
        "moduli": len(moduli_per_codice),
        "sessioni": n_sessioni,
        "persone": conn.execute("SELECT COUNT(*) c FROM persona").fetchone()["c"],
        "sessioni_senza_modulo": senza_modulo,
    }
