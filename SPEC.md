# Cicerone — functional specification

Replaces a hand-filled spreadsheet with a desktop application. The spreadsheet
remains only as the source of the initial data: after the migration it is not
touched again.

## Origin

The original request had three points:

1. a link with the mail program, for calendar invitations;
2. an automatic step that at the end of the day marks a session as held and
   passed;
3. a guarantee that renaming a tutor does not break the file.

Point 3 was a real problem in the spreadsheet: the tutor's name was a string
used as a key by the formulas. In the app tutors are records with their own id,
and renaming somebody has no side effects.

## Decisions taken

| Topic | Decision |
|---|---|
| Scope | Multi-trainee: a reusable module catalogue, one plan per hire |
| Calendar invitation | Yes, an `.ics` attached to the message (since 2026-09-08; previously ruled out). Every session owns a `UID`: moving or cancelling touches **that** appointment, never another one between the same people. A move updates the existing invitation by raising `SEQUENCE`; it does not cancel and recreate. Microsoft Graph stays excluded: it would need credentials and IT involvement |
| Automatic completion | On application start-up. Marks `Svolta` plus outcome `OK` |
| Platforms | macOS and Windows, driving the mail program already installed |
| Delivery | Through the installed mail client (no credentials). SMTP as a possible fallback |

A note on certification: setting the outcome `OK` automatically attributes a
judgement of effectiveness that nobody expressed. The choice was confirmed
explicitly; sessions closed automatically stay flagged
`chiusa_automaticamente` in the database, so a review screen can be added later
without a migration.

## Data model

    persona            id, nome, cognome, email, reparto, attivo
                       -> tutors, managers and trainees are all people

    risorsa            id, persona_id, reparto, mansione, responsabile_id,
                       tutor_principale_id, data_inizio, motivo

    modulo_catalogo    codice (M01..M21), area, titolo, modalita_default,
                       tutor_referente_default_id, ordine
                       -> the template every new plan is created from

    area               nome, colore, ordine
                       -> the colour shown in the agenda and on the calendar

    piano              id, risorsa_id, creato_il, chiuso_il
    piano_modulo       id, piano_id, codice, area, titolo, applicabile (SI/NO),
                       modalita, tutor_referente_id,
                       entro_il, verifica_chiusura, verifica_efficacia,
                       data_verifica, esito
                       -> the last five are the form's manual columns

    sessione           id, piano_id, piano_modulo_id (nullable), data,
                       ora_inizio, ora_fine, dettaglio, stato, esito_verifica,
                       note, chiusa_automaticamente, sostituisce_id,
                       creata_il, modificata_il,
                       uid_calendario, revisione_calendario
                       stato: Pianificata | Confermata | Svolta | Rinviata | Annullata

    sessione_tutor     sessione_id, persona_id
                       -> many-to-many: in the spreadsheet every tutor of a
                          session sat in a single cell, comma separated

    mail_log           id, sessione_id, tipo, destinatari, oggetto, corpo,
                       registrata_il, inviata_il, esito, errore, senza_email,
                       calendario
                       tipo: nuova | spostamento | annullamento

    impostazione       chiave, valore
                       invio_email_automatico: 0 (default) | 1
                       canale_mail, mittente_mail, codice_modulo

Names are in Italian because they are domain identifiers written inside every
archive; the README carries the glossary.

## Calculation rules

One direction only: sessions are the facts, the plan is derived. No aggregate
value is ever written by hand.

For each module in the plan:

    valid_sessions = the module's sessions whose state is not Annullata, Rinviata
    planned        = count of valid_sessions
    done           = count of sessions with state Svolta
    hours_done     = sum of (ora_fine - ora_inizio) over the Svolta ones
    from / to      = minimum / maximum date of valid_sessions

    module state:
        applicabile = NO       -> N.A.
        planned = 0            -> Da pianificare
        done >= planned        -> Completata
        done > 0               -> In corso
        otherwise              -> Pianificata

Colours (inherited from the spreadsheet's conditional formatting, kept in the
interface): Svolta and Completata green `#C6EFCE`, In corso blue `#BDD7EE`,
Rinviata and Da pianificare orange `#FCE4D6`, Annullata pink `#F2DCDB`, N.A.
grey `#D9D9D9`.

## Automatic completion

Runs when the app starts, not at a fixed hour: at 18:00 the computer may be off.

A session is closed automatically if, all at once:

- its state is `Pianificata` or `Confermata`;
- it is in the past: `data < today`, or `data = today` and it is past 18:00;
- it has not been rescheduled, and no newer session replaces it.

Effect: state becomes `Svolta`, `esito_verifica` becomes `OK`,
`chiusa_automaticamente` becomes true. At start-up the app reports what it
closed, so the step stays auditable.

## Messages

Three events produce a message, always to the same recipients: the session's
tutors and the trainee.

- new session      -> day, time, module, tutors
- move             -> old **and** new day and time, side by side
- cancellation     -> the day and time called off

Each carries a calendar invitation. The message text comes from
`template_mail/`, editable without touching the code.

Automatic delivery is controlled by the toggle in the mail screen. The default
is off: composition and logging still happen, but no sender is called and the
entry stays in the log with outcome `invio_disattivato`. The main outcomes are
`inviata`, `invio_disattivato` and `errore`.

The log keeps `registrata_il`, the moment the notification was recorded.
`inviata_il` is only set after a successful delivery. Blocked or failed entries
can be retried; a retry reuses the subject, body, recipients and invitation
stored on the original entry and updates it in place rather than creating a
duplicate. Deleting from the log removes only the `mail_log` row.

The trainee's address and every tutor's are included and de-duplicated
case-insensitively, preserving order. Empty or whitespace-only values count as
missing addresses; full syntactic validation of addresses is out of scope.

Delivery goes through the installed mail client: COM on Windows, AppleScript on
macOS. When no client is configured the message is written to
`dati/mail_non_inviate/` instead of being sent, so nothing is lost.

## Still open

1. The email addresses of tutors and trainees. Without them the automation has
   no recipients.
2. The final text of the three messages.
3. Sessions with no module assigned have to be attributed from the app.
4. Whether the form still has to be printed and signed: if so, the app exports
   it to PDF with the same layout.
