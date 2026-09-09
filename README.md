# Cicerone

A desktop app for onboarding new hires: the agenda of their training sessions,
the certification training plan, and automatic notifications — each carrying a
calendar invitation — whenever an appointment is created, moved or cancelled.

It replaces a spreadsheet filled in by hand, and fixes its main flaw: in the
spreadsheet the totals and the statuses were typed in and could contradict the
rows below them. Here **the plan is calculated**, so it cannot disagree with
itself.

The name comes from the *cicerone*, the guide who shows a newcomer around: that
is the tutor's job.

> **A note on language.** Code, comments and documentation are in English. The
> user interface, the message templates and the printed form are in Italian,
> because the people using the program are: that part is product content, not
> code. A few identifiers stay Italian too — see [Glossary](#glossary).

## If you just want to use it

Nothing to install: no Python, no runtime. You get one package and double-click
it. Step-by-step instructions, in Italian, are in
**[docs/istruzioni.pdf](docs/istruzioni.pdf)**.

1. Unzip `Cicerone-v1.2.0.zip` and move **Cicerone** where you keep your programs.
2. Open it.
3. On first run the app asks **which mail program** the notifications should be
   sent from, and lets you send a test before confirming.

Automatic delivery starts **switched off**: notifications are composed and
logged but not sent until you turn it on from the *Mail inviate* tab. That is
deliberate — it lets you see what the app would send before letting it write to
your colleagues.

## If you want to work on it

Python 3.12 or newer.

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python seed_demo.py     # invented data, for development
    .venv/bin/python run.py           # the app window

On Windows the commands are `.venv\Scripts\python`.

Server only, reloading on every save:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8731

The tests — 112 of them, covering the plan calculation, automatic closing, clash
detection, delivery and archive upgrades:

    .venv/bin/python -m unittest discover -s app -p "test_*.py"

## What it does

**Agenda** — sessions day by day. Days already past are folded away. The colour
on the left says which **area** the module belongs to, not the state of the
session.

**Week** — the same sessions on a calendar, always opening on the current week.

**Training plan** — the plan, computed: one row per module, with dates, counts,
hours and status derived from the sessions alone. The assessment columns stay
editable by hand, because they are a person's judgement. It exports to PDF in
the shape of the quality-system form, ready to sign.

When the induction is over the plan is **declared finished**. From then on it
stops changing: it no longer follows the module catalogue, automatic completion
leaves its sessions alone, and the app refuses to write to it — which is the
point, because the plan is a certification record. It can be reopened if
something needs correcting.

**Modules** — the catalogue every new hire's plan is created from, with the
colour of each area.

**People** — the address book. One person has a name and an email, and can be a
tutor on one plan and the trainee on another: there are not two separate records.

**Sent mail** — the log of every notification: when, to whom, with what text and
with what outcome. From here you can re-read what was sent, retry what did not
go out, and switch automatic delivery on or off.

## Notifications and calendar invitations

They go out in three cases: a session created, moved, or cancelled. They reach
the session's tutors **and** the person being trained.

Every notification carries a **calendar invitation**, not just text: the
recipient gets an appointment to accept. Each session owns an identifier,
generated once: moving or cancelling touches **that** appointment. Two meetings
between the same people — which happens when a long topic is split in two —
cannot be confused. A move **updates** the existing appointment rather than
cancelling and recreating it, so nothing vanishes and reappears in anyone's
calendar.

The app holds no mail credentials and talks to no server: it drives the mail
program already configured on the computer — Outlook on Windows, Outlook or Mail
on macOS. The message therefore goes out from the person, and there is no
service mailbox to have created.

One detail that matters: **"no error" does not mean "sent"**. A mail program can
accept a message and leave it in the outbox, or lose it if it has no account
configured. After sending, the app checks that the message really left the
outbox, and if it is still sitting there it records an error rather than a
delivery.

## The data

Everything lives in a single file, `piano.db`, on the computer of whoever uses
the program. It is not in this repository, deliberately: it holds names,
addresses and training records of real people.

- macOS: `~/Library/Application Support/Cicerone/dati/`
- Windows: next to the executable

The app keeps **one copy a day** at start-up, in `dati/copie/`, retaining the
last ten, plus **one copy before any upgrade** that touches the archive's shape.
That is the only safety net there is, because that file is on no server.

For development, `seed_demo.py` generates invented names on the `@esempio.test`
domain.

### What is in the sample data, and what is not

`seed_demo.py` creates a complete, realistic archive — one trainee, 21 modules,
28 sessions over five weeks, some already held — because a project that starts
empty cannot be tried out and the tests need something to run against. Two of
the generated people are **deliberately left without an email address**, so the
warning the app raises can be verified rather than assumed.

The data is invented and the training catalogue is **deliberately generic**: it
describes an induction as any manufacturing company might run it. A real
catalogue is confidential — it says what a company makes, in which lines, and
how it is organised inside — so it does not live in the code. It reaches the
archive in one of two ways: loaded from a spreadsheet with
`import_spreadsheet.py`, or typed in from the **Modules** tab.

The same goes for the **form code** printed at the top of the PDF: every company
has its own, taken from its quality system, and it identifies the company. The
code carries only a placeholder (`MOD-FORM-01`); the real one is set once from
the *Codice del modulo* field in the training plan tab, and stays in the archive.

The rule, in short: **the repository holds the program and invented data; real
data and anything identifying an organisation live in the local archive, which
is not version-controlled.**

## Upgrading without losing anything

A new version of the app **adapts** the existing archive, it does not recreate
it. Every archive records which schema version it is at, and on start-up only
the missing migrations are applied, after a copy has been put aside.

Anyone touching the schema adds a migration: the procedure and the rules are in
[CLAUDE.md](CLAUDE.md), the tests in `app/test_upgrades.py`.

## How it is built

    app/db.py          schema, migrations and archive backups
    app/paths.py       where resources and data live, in development and packaged
    app/rules.py       plan calculation, automatic closing, clash detection
    app/pdf_export.py  the PDF of the certification form
    app/messages.py    composing the messages from the templates
    app/invites.py     iCalendar invitations
    app/delivery.py    the mail programs, and the check that a message really left
    app/importer.py    one-off reading of the original spreadsheet
    app/main.py        API and server
    app/web/           interface: three files, no framework, no build step
    template_mail/     the three message texts, editable without touching code

The server is local and the window is native: this is not a website and it needs
no connection. The interface uses no framework and no CDN, and the font and
icons live inside the program, because it has to work offline.

## Building the package

PyInstaller does not cross-compile: the macOS package is built on macOS, the
Windows one on Windows. Both can be produced from the workflows in
`.github/workflows/`, started from the **Actions** tab.

Locally, on macOS:

    .venv/bin/pyinstaller --clean --noconfirm Cicerone.spec
    ditto --norsrc --noextattr --noqtn dist/Cicerone.app /tmp/C.app
    codesign -s - --force --deep /tmp/C.app
    rm -rf dist/Cicerone.app && ditto /tmp/C.app dist/Cicerone.app

The `ditto` and `codesign` steps are not optional: on an Apple-silicon Mac an
unsigned package **will not start**, and the extended attributes the system
attaches to files make the signing fail.

To hand it over, compress it rather than copying the folder:

    ditto -c -k --keepParent dist/Cicerone.app Cicerone-v1.2.0.zip

A USB stick formatted for Windows (FAT32 or exFAT) does not preserve the execute
permission: copying the open package onto one leaves it unable to start on the
other computer. Inside a zip the permissions travel as data and arrive intact.

The icon is regenerated from the logo with `make_icon.py`, and the user guide
with `make_guide.py` (both need Pillow, which is used only for that and does not
enter the package).

## Glossary

Some identifiers stay in Italian on purpose, because they are **domain
identifiers**: they are written inside every existing archive, and renaming them
in the code would leave code and data disagreeing.

| Italian | Meaning |
|---|---|
| `persona` | a person: tutor, manager or trainee |
| `risorsa` | the person being trained (the "resource" of the original form) |
| `piano` / `piano_modulo` | the training plan, and one module within it |
| `sessione` | a single training session |
| `modulo_catalogo` | the reusable catalogue a plan is created from |
| `area` | the training area a module belongs to, and its colour |
| `mail_log` | the record of every notification |
| `Pianificata`, `Svolta`, `Annullata`, `Rinviata` | session states, stored as written |

The same applies to the response keys that mirror those columns, and to the
template variables (`{{ risorsa }}`, `{{ data_estesa }}`), which are the contract
with the Italian message templates.

## Licence

MIT — see [LICENSE](LICENSE).

## Before working on it

[CLAUDE.md](CLAUDE.md) gathers the domain rules that cannot be deduced from the
sources, and the mistakes that cost the most. [ROADMAP.md](ROADMAP.md) says what
is missing. [SPEC.md](SPEC.md) records the decisions taken and why.
