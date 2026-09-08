"""Calendar invitations, in iCalendar format.

A plain message says when you are meeting; an invitation writes it into the
recipient's calendar and keeps it up to date. That is the difference between
telling someone and booking them.

The delicate part is **which** appointment gets touched. Every session owns a
`UID`, generated once and stored in the database: the recipient's calendar uses
it to know what to update or cancel. Two sessions between the same people —
which happens when a long topic is split across two meetings — carry different
UIDs, so moving the first cannot disturb the second.

Hence the three rules:

- **moving is not cancelling.** The same UID is sent again with a higher
  `SEQUENCE`, and the calendar moves the appointment where it stood. Cancelling
  and recreating would make the commitment vanish and reappear, and on one of
  two sessions it would also be easy to hit the wrong target;
- **the sequence number must always go up**, otherwise calendars discard the
  update as a duplicate they have already seen;
- **`METHOD:CANCEL` only for cancellations**, with the same UID.

Times travel in UTC (`...Z`): without an explicit zone an invitation read from
another country would land at the wrong hour.
"""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Rome")
PRODUCT_ID = "-//Cicerone//Training Plan//EN"


def new_uid() -> str:
    """An appointment identifier, unique even across installations."""
    return f"{uuid.uuid4()}@cicerone"


def _utc(day: str, clock: str) -> str:
    """'2026-09-10' + '09:30' -> '20260910T073000Z' (local time converted)."""
    local = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE)
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def _escape(value: str | None) -> str:
    """Protects the characters that separate fields in iCalendar."""
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Wraps long lines as the standard requires (75 octets).

    Outlook forgives long lines, other calendars do not: better not to find
    that out from somebody else's computer.
    """
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks, current = [], b""
    for character in line:
        encoded = character.encode("utf-8")
        # from the second line on there is the leading space of the continuation
        limit = 75 if not chunks else 74
        if len(current) + len(encoded) > limit:
            chunks.append(current.decode("utf-8"))
            current = b""
        current += encoded
    chunks.append(current.decode("utf-8"))
    return "\r\n ".join(chunks)


def compose(
    uid: str,
    sequence: int,
    day: str,
    start_time: str,
    end_time: str,
    title: str,
    description: str,
    organiser: str | None,
    attendees: list[dict],
    cancelled: bool = False,
    location: str | None = None,
) -> str:
    """The invitation text, ready to attach.

    `attendees` are dictionaries with `nome` and `email`. With `cancelled` a
    cancellation is sent for that same appointment, not for another one.
    """
    method = "CANCEL" if cancelled else "REQUEST"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODUCT_ID}",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{datetime.now(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{_utc(day, start_time)}",
        f"DTEND:{_utc(day, end_time)}",
        f"SUMMARY:{_escape(title)}",
        f"DESCRIPTION:{_escape(description)}",
        "STATUS:" + ("CANCELLED" if cancelled else "CONFIRMED"),
        "TRANSP:OPAQUE",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    if organiser:
        lines.append(f"ORGANIZER:mailto:{organiser}")
    for person in attendees:
        address = (person.get("email") or "").strip()
        if not address:
            continue
        name = _escape(person.get("nome") or address)
        lines.append(
            f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;"
            f'PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN="{name}":mailto:{address}'
        )
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def file_name(kind: str, session_id: int) -> str:
    return f"training-{session_id}-{kind}.ics"
