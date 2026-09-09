"""Where resources and data live, both in development and inside the bundle.

PyInstaller unpacks read-only resources into a temporary folder that disappears
when the program exits, so user data cannot live there. Hence:

- read-only resources (the interface, the original templates) travel inside the
  bundle;
- the database, the messages and the edited templates live outside, where they
  survive between runs.

Where that "outside" is depends on the platform, and the two conventions differ:
next to the executable on Windows, in the user's own folder on macOS. See
`data_folder`.
"""

import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

APP_NAME = "Cicerone"

# The one place the version is written. `Cicerone.spec` reads it from here when
# it builds the package, and `/api/state` hands it to the interface, so the
# number on screen is always the number that was built. Packages travel by hand
# on a USB stick: "which version is she running?" has to be answerable without
# opening the bundle.
VERSION = "1.2.0"


def resource_folder() -> Path:
    """Where the files the program reads, and never writes, are kept."""
    if FROZEN:
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def data_folder() -> Path:
    """Where the program writes: never inside the bundle.

    On macOS an `.app` is read-only by convention: writing inside it
    invalidates its signature, and under `/Applications` the permission is
    often missing altogether. The database would end up in
    `Cicerone.app/Contents/MacOS/`, which is the wrong place: it would vanish
    with every update. On macOS we therefore use the user's own folder, which
    is also where the Mac expects to find it.

    On Windows the data stays next to the executable instead: that is the
    behaviour already documented to the people using the program, and changing
    it now would abandon a database that is already in use.

    In development, frozen or not, we stay in the project folder.
    """
    if not FROZEN:
        return Path(__file__).resolve().parent.parent
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(sys.executable).resolve().parent


def template_folder() -> Path:
    """The message templates, in a folder the user can edit.

    On the bundle's first run they are copied next to it: from there they can
    be opened in a text editor and reworded without rebuilding anything.
    """
    destination = data_folder() / "template_mail"
    if not destination.exists():
        source = resource_folder() / "template_mail"
        if source.exists():
            shutil.copytree(source, destination)
    return destination
