# What is missing

The state of the project, in order of usefulness. What already works is
described in the [README](README.md); this is the rest.

## Before installing it on a new computer

1. **A delivery test on the target machine.** The app drives the mail program
   already configured there, and which one that is changes from computer to
   computer: the setup screen, on first run, allows a real test before
   confirming. Until that test has succeeded on that machine, delivery is not
   verified.

2. **The email addresses in the address book.** Without them notifications have
   no recipients: the app says so at the top and does not fail silently, but the
   data is needed.

3. **The final message texts.** The ones in `template_mail/` are working
   placeholders, editable without touching the code.

4. **Deciding whether automatic delivery ships switched on.** The default is
   off, which is the right choice during development; at handover it has to be
   decided.

## Signing the package

The package is signed "ad-hoc": enough to make it start, but not enough to avoid
the macOS warning the first time a file downloaded from the internet is opened.
With an Apple developer account it can be signed and notarised, and the warning
goes away.

Without an account there is a free path that works: hand the package over on a
**USB stick** or from a network folder rather than downloading it. The warning is
triggered by the label macOS attaches to files fetched from the internet; coming
from local media, that label is not there.

Mind the format of the medium: a FAT32 or exFAT stick does not preserve execute
permissions, so the package has to travel **inside a zip**, where the permissions
are carried as data.

## Later on

1. **A fallback SMTP channel**, in case the mail program blocks automation. The
   interface in `app/delivery.py` is ready for it: a class with `available()`
   and `send()` is all it takes.
2. **A reminder the day before** a session.
3. **Export and import of the archive** from the interface, for moves and
   restores without going through a terminal.
4. **Search and filters in the agenda**, by person, area or state.
5. **Archiving completed plans**, so the list stays readable over time.
6. **Updating the app** without replacing the package by hand.
7. **A change history** for a session: for certification purposes that is worth
   as much as the delivery log.
8. **Statistics**: hours per area, average time to completion.

## Technical debt

- The tests run in the macOS workflow but not in the Windows one. `pytest` is
  not among the dependencies: the suite is `unittest` and runs with
  `python -m unittest discover -s app -p "test_*.py"`.
- Waiting for the message to leave the mail program's outbox can take up to half
  a minute. It no longer blocks the interface, but somebody watching the setup
  screen still waits with little feedback.
- The frontend has no automated tests. It is three files with no build step and
  the logic in them is thin, but a change to the API routes is only caught by
  opening the app.
- `app/importer.py` reads the original spreadsheet: throwaway code for the
  initial migration, and it has no tests.
