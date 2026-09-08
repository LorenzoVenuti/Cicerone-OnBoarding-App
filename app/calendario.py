"""Inviti per il calendario, in formato iCalendar.

Una mail di testo dice quando ci si vede; un invito lo scrive nel calendario di
chi lo riceve, e lo tiene aggiornato. E' la differenza fra avvisare e fissare.

Il punto delicato e' **quale** appuntamento si tocca. Ogni sessione ha un `UID`
suo, generato una volta e conservato nel database: il calendario del
destinatario usa quello per sapere cosa aggiornare o disdire. Due sessioni fra
le stesse persone, magari sullo stesso argomento spezzato in due incontri, hanno
UID diversi: spostare la prima non puo' toccare la seconda.

Da qui le tre regole:

- **spostare non e' disdire.** Si rimanda lo stesso UID con `SEQUENCE` piu'
  alta e il calendario sposta l'appuntamento dov'era. Disdire e ricreare
  farebbe sparire e ricomparire l'impegno, e su una sola delle due sessioni
  sarebbe anche facile sbagliare bersaglio;
- **la revisione va sempre alzata**, altrimenti i calendari scartano
  l'aggiornamento credendolo un doppione gia' visto;
- **`METHOD:CANCEL` solo per l'annullamento**, con lo stesso UID.

Gli orari viaggiano in UTC (`...Z`): senza fuso esplicito un invito letto da un
altro paese finirebbe nell'ora sbagliata.
"""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("Europe/Rome")
PRODOTTO = "-//Cicerone//Piano Formazione//IT"


def nuovo_uid() -> str:
    """Identificativo di un appuntamento, unico anche fra installazioni diverse."""
    return f"{uuid.uuid4()}@cicerone"


def _quando(data: str, ora: str) -> str:
    """'2026-09-10' + '09:30' -> '20260910T073000Z' (ora locale convertita)."""
    locale = datetime.strptime(f"{data} {ora}", "%Y-%m-%d %H:%M").replace(tzinfo=FUSO)
    return locale.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def _testo(valore: str | None) -> str:
    """Mette in salvo i caratteri che in iCalendar separano i campi."""
    return (
        (valore or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _piega(riga: str) -> str:
    """Spezza le righe lunghe come vuole lo standard (75 ottetti).

    Outlook perdona le righe lunghe, altri calendari no: meglio non scoprirlo
    dal computer di qualcun altro.
    """
    grezza = riga.encode("utf-8")
    if len(grezza) <= 75:
        return riga
    pezzi, corrente = [], b""
    for carattere in riga:
        codificato = carattere.encode("utf-8")
        # dalla seconda riga in poi c'e' lo spazio iniziale della continuazione
        limite = 75 if not pezzi else 74
        if len(corrente) + len(codificato) > limite:
            pezzi.append(corrente.decode("utf-8"))
            corrente = b""
        corrente += codificato
    pezzi.append(corrente.decode("utf-8"))
    return "\r\n ".join(pezzi)


def componi(
    uid: str,
    revisione: int,
    data: str,
    ora_inizio: str,
    ora_fine: str,
    titolo: str,
    descrizione: str,
    organizzatore: str | None,
    partecipanti: list[dict],
    annullato: bool = False,
    luogo: str | None = None,
) -> str:
    """Il testo dell'invito, pronto da allegare.

    `partecipanti` sono dizionari con `nome` ed `email`. Con `annullato` si
    manda una disdetta dello stesso appuntamento, non di un altro.
    """
    metodo = "CANCEL" if annullato else "REQUEST"
    righe = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODOTTO}",
        "CALSCALE:GREGORIAN",
        f"METHOD:{metodo}",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SEQUENCE:{revisione}",
        f"DTSTAMP:{datetime.now(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{_quando(data, ora_inizio)}",
        f"DTEND:{_quando(data, ora_fine)}",
        f"SUMMARY:{_testo(titolo)}",
        f"DESCRIPTION:{_testo(descrizione)}",
        "STATUS:" + ("CANCELLED" if annullato else "CONFIRMED"),
        "TRANSP:OPAQUE",
    ]
    if luogo:
        righe.append(f"LOCATION:{_testo(luogo)}")
    if organizzatore:
        righe.append(f"ORGANIZER:mailto:{organizzatore}")
    for persona in partecipanti:
        indirizzo = (persona.get("email") or "").strip()
        if not indirizzo:
            continue
        nome = _testo(persona.get("nome") or indirizzo)
        righe.append(
            f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;"
            f'PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN="{nome}":mailto:{indirizzo}'
        )
    righe += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_piega(riga) for riga in righe) + "\r\n"


def nome_file(tipo: str, sessione_id: int) -> str:
    return f"formazione-{sessione_id}-{tipo}.ics"
