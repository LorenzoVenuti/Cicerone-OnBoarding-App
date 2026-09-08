# Notes for anyone working on this project

Read this before touching the code. It holds the domain rules you cannot deduce
from the sources, and the mistakes that cost the most.

## What it is

A desktop app for onboarding new hires: the agenda of their training sessions,
the training plan required by the quality certification, and the automatic
notifications sent when an appointment is created, moved or cancelled.

It grew out of a spreadsheet filled in by hand. That spreadsheet is no longer
the source: it was imported once and should be considered superseded. Do not
write code that reads or updates spreadsheets, with the single exception of
`app/importer.py`, which exists for that initial migration.

Whoever uses the program is not a technical person and will never open a
terminal: everything has to be reachable from the interface.

## Language

Code, comments and documentation are in **English**. Three things stay in
Italian, deliberately:

- **the interface** and the message templates in `template_mail/`, because the
  people using the program are Italian — that is product content;
- **the printed form**, which is filed as a certification record;
- **domain identifiers**: table and column names, session states, the response
  keys that mirror those columns, and the template variables. They are written
  inside every existing archive, so renaming them in the code would leave code
  and data disagreeing. The README carries the glossary.

When you add a message the user will read, write it in Italian. When you name a
function or a variable, name it in English.

## Getting started

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python seed_demo.py     # invented data to work with
    .venv/bin/python run.py           # the app window

Server only, with auto-reload:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8731

On Windows the commands are `.venv\Scripts\python`.

## Where things are

    app/db.py          schema, migrations and archive backups
    app/paths.py       where resources and data live, in development and packaged
    app/rules.py       plan calculation, automatic closing, clash detection
    app/pdf_export.py  the PDF of the certification form
    app/messages.py    composing the messages from the templates
    app/invites.py     iCalendar invitations
    app/delivery.py    the mail programs, and the check that a message really left
    app/importer.py    one-off reading of the original spreadsheet
    app/main.py        the HTTP API and the server
    app/web/           interface: three files, no framework, no build step
    template_mail/     the message texts, editable without touching code
    seed_demo.py       generates invented data
    SPEC.md            functional specification and decisions taken

## The rules not to break

**1. The plan is calculated, never written.**
Sessions are the only facts. Dates, counts, hours and each module's status are
derived from them, in `rules.module_summary`. Do not add aggregate columns to
the database "for convenience or speed": duplicating something computable is
exactly the flaw of the spreadsheet this app replaces. With a few dozen sessions
per plan, recomputing costs nothing.

**2. Automatic closing runs at start-up, not at a fixed time.**
The requirement mentions 18:00, but a desktop machine may be switched off then.
`rules.close_past_sessions` is called when the app starts and catches up on
every day left behind. It must stay idempotent: running it twice must change
nothing the second time. It closes a session only if it is still open, is in the
past, and nobody rescheduled it. It marks `Svolta` plus outcome `OK` and leaves
`chiusa_automaticamente` at 1: that flag distinguishes a human judgement from an
automatic one — do not drop it.

**3. Tutors and trainees are the same kind of record.**
There are not two separate directories: a person has a name, a surname and an
email, and can be a tutor on one plan, the trainee of another, or both. They are
created and edited from the People tab. The email is what makes notifications
possible: a change of plan goes to the session's tutors **and** to the person
being trained, not just to the coach.

**4. People are referred to by identity, never by name.**
In the spreadsheet the tutor was a string used as a key, and renaming somebody
broke the sheet: a real problem, reported by the user. Every reference to a
person goes through `persona.id`. A session can have several tutors: the
relation is `sessione_tutor`, not a text field.

**5. Sessions are never deleted.**
They are cancelled, staying in the plan with state `Annullata`. The training
plan is a certification document: it has to show what was called off too.

**6. Clashes are flagged, not prevented.**
`rules.overlaps` finds collisions for the trainee and for the tutors; the
interface shows them while you type, and still lets you save. Sometimes two
overlapping commitments are intentional, and a program that forbids them gets
worked around.

**7. Colour means the area, not the state.**
In the agenda (left border) and on the calendar (block background) the colour
says which training area the module belongs to — Commercial, IT, Engineering —
not the state of the session. The colour lives on the `area` table, assigned by
default by `rules.ensure_area_colours`, which runs at start-up and is
idempotent: an old archive fills itself in without a hand-written migration. It
is changed from the Modules tab and applies to every module in that area. State
stays in the text badges; on the calendar a cancelled session is struck through
and dimmed. The calendar always opens on the current week, never on the plan's
first session.

**8. Notifications carry a calendar invitation.**
Not just text: an `.ics` that writes the appointment into the tutors' and the
trainee's calendars. Every session has a `uid_calendario`, generated once and
never changed, plus a `revisione_calendario` that goes up with every
notification. They serve one decisive purpose: **moving or cancelling touches
that appointment and no other**. Two meetings between the same people — which
happens when a long topic is split — have different UIDs, so cancelling the
first does not remove the second. A move **updates** the existing invitation
(same UID, higher sequence): it is not cancelled and recreated, or the
commitment would vanish and reappear in the recipient's calendar.
`METHOD:CANCEL` is only for cancellations. Without raising the sequence,
calendars discard the update as a duplicate.

**9. The mail program is not guessed: it is configured.**
A computer can hold both Outlook and Mail, one with the work account and the
other empty, and from the outside they look alike: Outlook's profile can weigh
hundreds of megabytes without a single active account. On first run the app asks
the installed programs (`delivery.available_channels`), shows which addresses
they hold, lets the user choose, and stores the choice in `impostazione`
(`canale_mail`, `mittente_mail`). Until that is done, `mail_configured` is false
and the interface asks.

**10. "No error" does not mean "sent".**
AppleScript reports success even when the message is only queued, or when the
client accepts it and loses it for want of an account — this was observed, not
imagined. Recording that as a delivery is the worst possible defect here,
because the log would say "sent" and nobody would ever learn otherwise. After
`send`, the scripts check that the message **left the outbox**, and if it is
still there that is an error. Do not remove that check to make sending faster.

Automatic delivery is a central policy, stored in `impostazione`, and it
defaults to **off**. Even with delivery off the notification is composed and
recorded in `mail_log` as `invio_disattivato`; the sender is not called. Every
entry keeps `registrata_il`; `inviata_il` is only set after a successful
delivery. Blocked or failed entries can be retried from the log, and deleting an
entry deletes only the log row, never the session.

## Data and confidentiality

The repository holds **no real data**, by choice. Names, addresses and training
records of real people end up in the database.

- `dati/`, the `.db` files and the `.xlsx` files are in `.gitignore`. Leave them
  out.
- Do not write real names, email addresses or product names into the code, the
  comments, the tests or the commit messages.
- To try something out use `seed_demo.py`: invented names on the
  `@esempio.test` domain, and two people deliberately without an email so the
  warning can be exercised.
- The training catalogue and the form code identify a company: they belong in
  the archive, not in the code. See the README.

## Conventions

- Commit messages in English, imperative present (`Add PDF export`).
- No emoji, anywhere.
- The interface uses no framework and has no build step: three files in
  `app/web/`. Do not introduce React, a bundler or a CDN dependency without a
  strong reason — the app has to work offline.
- For the same reason the font and icons live inside the program: Inter sits in
  `app/web/font/` (variable font, one file, SIL Open Font License) and the icons
  are hand-written SVG shapes in `app/web/app.js`.
- The CSS and JavaScript references in `index.html` carry a `?v=N`. Raise it
  when you change the page: the server already sends `no-store`, but a stale
  cache surviving an update is a day lost hunting a bug that does not exist.
- The endpoints in `app/main.py` are `async def` on purpose: FastAPI then runs
  them on the event loop's single thread, and the shared SQLite connection stays
  safe. Add a synchronous one and the first database access will fail with
  "SQLite objects created in a thread can only be used in that same thread".
- Anything that waits on the mail program goes through
  `delivery.send_without_blocking`: waiting for the outbox can take tens of
  seconds, and on the event loop the whole interface would freeze.

## Checking a change

    .venv/bin/python -m unittest discover -s app -p "test_*.py"

Ninety tests cover the plan calculation, automatic closing, clash detection,
delivery policy, the macOS channels and archive upgrades. If you touch
`rules.py`, add to `app/test_rules.py`.

If you change the schema, **add a migration**: editing `SCHEMA` alone is not
enough, because `CREATE TABLE IF NOT EXISTS` does not touch existing tables and
the new column would never appear in an existing archive. Write
`_migration_N(conn)` and append it to `MIGRATIONS`; the number ends up in
`PRAGMA user_version`, so every archive knows where it stands. Before applying
them the app puts a copy in `dati/copie/`. Published migrations are never
edited: they have already run on computers you do not have, and they must be
safe to run twice. The tests are in `app/test_upgrades.py`.
