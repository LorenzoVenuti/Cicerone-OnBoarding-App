# What is missing

The state of the project, in order of usefulness. What already works is
described in the [README](README.md); this is the rest.

Items marked **(seen)** were observed on a running build, not guessed. The rest
are proposals, and some of them may not be worth doing — say so and delete the
line rather than leaving it here for years.

## Before handing it to somebody new

1. **A delivery test on that machine.** The app drives the mail program already
   configured there, and which one that is changes from computer to computer:
   the setup screen allows a real test before confirming. Until that test has
   succeeded on that machine, delivery is not verified.

2. **The email addresses in the address book.** Without them notifications have
   no recipients: the app says so at the top and does not fail silently, but the
   data is needed.

3. **The final message texts.** The ones in `template_mail/` are working
   placeholders, editable without touching the code.

4. **Deciding whether automatic delivery ships switched on.** The default is
   off, which is the right choice while the archive is being filled; at some
   point it has to be turned on deliberately.

## Functionality

1. **A change history for a session.** For certification purposes it is worth as
   much as the delivery log: today you can see that a session moved, but not
   when, nor from what.

2. **Search and filters in the agenda**, by person, area or state. Today the
   agenda has neither — with one trainee that is fine, with ten it is not.

3. **Archiving completed plans**, so the list of trainees stays readable. A plan
   can be declared finished since 1.2.0; hiding the finished ones from the
   picker is the part still missing.

4. **A reminder the day before** a session.

5. **Export and import of the archive** from the interface, for moving to
   another computer or restoring a backup without a terminal. Today the copies
   in `dati/copie/` can only be restored by hand.

6. **A fallback SMTP channel**, in case the mail program blocks automation. The
   interface in `app/delivery.py` is ready for it: a class with `available()`
   and `send()` is all it takes.

7. **Statistics**: hours per area, average time to completion.

8. **Updating the app** without replacing the package by hand.

## Interface and what you see

1. **Four notices can stack at the top at once** — **(seen)**: mail not
   configured, sessions closed automatically, people without an email, automatic
   delivery off. On a fresh archive they take up a third of the window before any
   content, and two of them say nearly the same thing. They are dismissable one
   by one, which does not help on first run, when they all appear together.
   Worth collapsing into a single bar with a count, or at least merging the two
   about delivery.

2. **The layout wraps badly in a narrow window** — **(seen at 800 px)**: the tab
   labels break onto two lines and a session's module title stacks one word per
   line. The window can be resized freely, so this is reachable. A minimum width,
   or a tighter breakpoint, would fix it.

3. **Nothing shows that a long operation is running.** Waiting for the mail
   program to empty its outbox can take tens of seconds. It no longer blocks the
   interface, but somebody watching the setup screen waits with little feedback.

4. **Accessibility has barely been looked at** — **(seen)**: the session rows
   got proper `aria-label`s in 1.2.0, but the rest of the interface has almost
   none and keyboard navigation has never been tried. Not urgent for one user,
   and dishonest to leave unwritten.

## Look and feel

The interface is deliberately plain and it works; none of this is a defect.

1. **The empty states are good and the setup dialog is genuinely well done** —
   **(seen)**: it lists each mail program with the addresses it holds and says in
   red when one has none. Keep that standard when adding screens.

2. **Colour currently carries meaning in two places** — the area (agenda border,
   calendar block) and the state (text badges). It is documented and consistent,
   but it is the kind of thing to re-check before adding a third meaning.

3. **A print stylesheet.** The plan exports to PDF, but printing any other
   screen from the browser gives whatever the screen happens to look like.

4. **Density.** Rows are generously spaced, which suits a nearly empty archive
   and stops suiting one with fifty sessions. A compact mode is cheap to add and
   easy to get wrong; wait until the archive is big enough to judge.

## Code and infrastructure

1. **The frontend has no automated tests.** It is three files with no build step
   and thin logic, but a change to the API routes is only caught by opening the
   app — which is exactly how the route renaming was checked, by hand.

2. **`app/main.py` is 735 lines** and holds every route. Not a problem yet;
   splitting it by area (plan, sessions, people, mail) is the obvious move when
   it stops fitting in one reading.

3. **Italian identifiers left in the tests** — `self.cartella`,
   `self.risorsa_persona`, `self.altro_tutor` in
   [test_rules.py](app/test_rules.py). They survived the translation because the
   sweep looked at comments and docstrings, not local names. Cosmetic, but the
   language rule in CLAUDE.md says otherwise.

4. **The tests run in the macOS workflow but not in the Windows one.**

5. **`app/importer.py` has no tests.** Throwaway code for the initial migration,
   but it is the only thing that ever read the original spreadsheet.

6. **No changelog.** There are versioned releases now (1.0.0 to 1.2.0) and no
   file saying what changed between them. The commit messages carry it; a
   `CHANGELOG.md` would carry it where somebody looks.

7. **Dependencies are unpinned** (`requirements.txt` uses ranges), so two builds
   from the same commit can differ. Pinning would make a package reproducible,
   at the cost of updating the pins by hand.

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

## Decided against

Listed so nobody spends an afternoon re-proposing them.

- **An Apple developer account** (99 $/year): out of proportion for a handful of
  users. Revisit if the users multiply or updates become frequent.
- **Microsoft Graph** for sending mail: it would need credentials and the IT
  department. Driving the installed mail client keeps the app credential-free.
- **Reading or writing spreadsheets**, beyond the one-off `app/importer.py`. The
  spreadsheet is superseded, not a second source of truth.
- **A frontend framework, a bundler or a CDN dependency.** The app has to work
  offline on somebody's laptop.
