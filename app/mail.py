"""Composizione e invio delle mail di notifica.

I template stanno in `template_mail/`, come file di testo modificabili senza
toccare il codice: la prima riga e' l'oggetto, il resto e' il corpo.
I testi definitivi li fornisce chi usa il programma; questi sono segnaposto.
"""

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime

from jinja2 import Template

from . import calendario
from .percorsi import cartella_template

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

def data_estesa(iso: str) -> str:
    """'2026-09-07' -> 'lunedi 7 settembre 2026'."""
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"

def _carica_template(tipo: str) -> tuple[Template, Template]:
    testo = (cartella_template() / f"{tipo}.txt").read_text(encoding="utf-8")
    prima_riga, _, corpo = testo.partition("\n")
    oggetto = prima_riga.removeprefix("OGGETTO:").strip()
    return Template(oggetto), Template(corpo.strip())

def contesto_sessione(conn: sqlite3.Connection, sessione_id: int) -> dict:
    sessione = conn.execute(
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
        (sessione_id,),
    ).fetchone()
    if sessione is None:
        raise ValueError(f"sessione {sessione_id} inesistente")

    tutor = conn.execute(
        """
        SELECT p.id, p.nome, p.cognome, p.email
        FROM sessione_tutor st JOIN persona p ON p.id = st.persona_id
        WHERE st.sessione_id = ?
        ORDER BY p.cognome
        """,
        (sessione_id,),
    ).fetchall()

    modulo = (
        f"{sessione['codice']} - {sessione['modulo_titolo']}"
        if sessione["codice"]
        else (sessione["dettaglio"] or "Da assegnare")
    )

    return {
        "risorsa": f"{sessione['risorsa_nome']} {sessione['risorsa_cognome']}",
        "risorsa_email": sessione["risorsa_email"],
        "data": sessione["data"],
        "data_estesa": data_estesa(sessione["data"]),
        "ora_inizio": sessione["ora_inizio"],
        "ora_fine": sessione["ora_fine"],
        "modulo": modulo,
        "dettaglio": sessione["dettaglio"],
        "note": sessione["note"],
        "tutor": ", ".join(f"{t['nome']} {t['cognome']}" for t in tutor) or "da assegnare",
        "tutor_righe": [dict(t) for t in tutor],
    }

def _appuntamento(
    conn: sqlite3.Connection,
    sessione_id: int,
    contesto: dict,
    tipo: str,
    destinatari_noti: list[dict],
    organizzatore: str | None,
) -> str:
    """L'invito per il calendario, con l'identificativo di questa sessione.

    L'UID nasce alla prima notifica e non cambia piu': e' quello che permette
    agli avvisi successivi di spostare o disdire *questo* appuntamento invece di
    un altro fra le stesse persone. La revisione sale a ogni avviso, altrimenti
    i calendari scartano l'aggiornamento credendolo un doppione.
    """
    riga = conn.execute(
        "SELECT uid_calendario, revisione_calendario FROM sessione WHERE id = ?",
        (sessione_id,),
    ).fetchone()

    uid = riga["uid_calendario"] or calendario.nuovo_uid()
    revisione = riga["revisione_calendario"] or 0
    if riga["uid_calendario"] is None:
        conn.execute(
            "UPDATE sessione SET uid_calendario = ? WHERE id = ?", (uid, sessione_id)
        )
    else:
        revisione += 1
        conn.execute(
            "UPDATE sessione SET revisione_calendario = ? WHERE id = ?",
            (revisione, sessione_id),
        )
    conn.commit()

    descrizione = "\n".join(
        parte for parte in [
            f"Modulo: {contesto['modulo']}",
            f"Tutor: {contesto['tutor']}",
            f"Risorsa in formazione: {contesto['risorsa']}",
            contesto.get("note") or "",
        ] if parte
    )
    return calendario.componi(
        uid=uid,
        revisione=revisione,
        data=contesto["data"],
        ora_inizio=contesto["ora_inizio"],
        ora_fine=contesto["ora_fine"],
        titolo=f"Formazione: {contesto['modulo']}",
        descrizione=descrizione,
        organizzatore=organizzatore,
        partecipanti=destinatari_noti,
        annullato=(tipo == "annullamento"),
    )


def componi(
    conn: sqlite3.Connection,
    sessione_id: int,
    tipo: str,
    precedente: dict | None = None,
    mittente: str = "Ufficio HR",
    organizzatore: str | None = None,
) -> dict:
    """Prepara oggetto, corpo, destinatari e invito. Non invia niente."""
    contesto = contesto_sessione(conn, sessione_id)
    contesto["mittente"] = mittente

    if precedente:
        contesto["data_precedente"] = precedente["data"]
        contesto["data_precedente_estesa"] = data_estesa(precedente["data"])
        contesto["ora_inizio_precedente"] = precedente["ora_inizio"]
        contesto["ora_fine_precedente"] = precedente["ora_fine"]

    tmpl_oggetto, tmpl_corpo = _carica_template(tipo)

    indirizzi: list[str] = []
    senza_email: list[str] = []
    invitati: list[dict] = []
    for tutor in contesto["tutor_righe"]:
        indirizzo = (tutor["email"] or "").strip()
        if indirizzo:
            indirizzi.append(indirizzo)
            invitati.append(
                {"nome": f"{tutor['nome']} {tutor['cognome']}", "email": indirizzo}
            )
        else:
            senza_email.append(f"{tutor['nome']} {tutor['cognome']}")
    email_risorsa = (contesto["risorsa_email"] or "").strip()
    if email_risorsa:
        indirizzi.append(email_risorsa)
        invitati.append({"nome": contesto["risorsa"], "email": email_risorsa})
    else:
        senza_email.append(contesto["risorsa"])
    destinatari = []
    visti: set[str] = set()
    for indirizzo in indirizzi:
        indirizzo = indirizzo.strip()
        chiave = indirizzo.casefold()
        if indirizzo and chiave not in visti:
            visti.add(chiave)
            destinatari.append(indirizzo)
    return {
        "tipo": tipo,
        "sessione_id": sessione_id,
        "oggetto": tmpl_oggetto.render(**contesto),
        "corpo": tmpl_corpo.render(**contesto),
        "destinatari": destinatari,
        "senza_email": senza_email,
        "calendario": _appuntamento(
            conn, sessione_id, contesto, tipo, invitati, organizzatore
        ),
    }

def registra(
    conn: sqlite3.Connection,
    messaggio: dict,
    esito: str,
    errore: str | None = None,
    mail_log_id: int | None = None,
) -> None:
    """Registra una notifica o aggiorna la voce originale durante un retry."""
    registrata_il = datetime.now().isoformat(timespec="seconds")
    inviata_il = registrata_il if esito == "inviata" else None
    valori = (
        messaggio["sessione_id"],
        messaggio["tipo"],
        "; ".join(messaggio["destinatari"]),
        messaggio["oggetto"],
        messaggio["corpo"],
        inviata_il,
        esito,
        errore,
        json.dumps(messaggio.get("senza_email", []), ensure_ascii=False),
        messaggio.get("calendario"),
    )
    if mail_log_id is None:
        conn.execute(
            """
            INSERT INTO mail_log
                (sessione_id, tipo, destinatari, oggetto, corpo, registrata_il,
                 inviata_il, esito, errore, senza_email, calendario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (valori[0], valori[1], valori[2], valori[3], valori[4],
             registrata_il, *valori[5:]),
        )
    else:
        conn.execute(
            """
            UPDATE mail_log
            SET sessione_id = ?, tipo = ?, destinatari = ?, oggetto = ?, corpo = ?,
                inviata_il = ?, esito = ?, errore = ?, senza_email = ?, calendario = ?
            WHERE id = ?
            """,
            (*valori, mail_log_id),
        )
    conn.commit()


def messaggio_da_log(riga: Mapping[str, object]) -> dict:
    """Ricostruisce il messaggio immutabile usato da un retry."""
    destinatari = [
        indirizzo.strip()
        for indirizzo in str(riga["destinatari"] or "").split(";")
        if indirizzo.strip()
    ]
    try:
        senza_email = json.loads(str(riga["senza_email"] or "[]"))
    except (TypeError, json.JSONDecodeError):
        senza_email = []
    return {
        "tipo": riga["tipo"],
        "sessione_id": riga["sessione_id"],
        "oggetto": riga["oggetto"],
        "corpo": riga["corpo"],
        "destinatari": destinatari,
        "senza_email": senza_email if isinstance(senza_email, list) else [],
        # lo stesso invito di prima: un retry non deve creare un appuntamento nuovo
        "calendario": riga["calendario"] if "calendario" in riga.keys() else None,
    }


def voce_log(riga: sqlite3.Row) -> dict:
    """Converte una riga del log in una risposta JSON con i dati accessori."""
    voce = dict(riga)
    try:
        voce["senza_email"] = json.loads(voce.get("senza_email") or "[]")
    except (TypeError, json.JSONDecodeError):
        voce["senza_email"] = []
    if not isinstance(voce["senza_email"], list):
        voce["senza_email"] = []
    return voce
