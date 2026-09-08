"""One-off import of the data from the original spreadsheet.

    python import_spreadsheet.py "/path/to/training-plan.xlsx"

Refuses to run when the database already holds data: the import happens once,
and repeating it would create duplicate plans.
"""

import sys
from pathlib import Path

from app import db, importer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    path = Path(sys.argv[1]).expanduser()
    if not path.exists():
        sys.exit(f"file not found: {path}")

    conn = db.initialise()
    if conn.execute("SELECT COUNT(*) c FROM piano").fetchone()["c"]:
        sys.exit(
            f"The database {db.DB_PATH} already holds plans.\n"
            "Delete it first if you want to import again from scratch."
        )

    outcome = importer.import_spreadsheet(path, conn)
    print(f"Imported the plan of {outcome['risorsa']}:")
    print(
        f"  {outcome['moduli']} modules, {outcome['sessioni']} sessions,"
        f" {outcome['persone']} people"
    )
    if outcome["sessioni_senza_modulo"]:
        print("\nSessions with no module assigned, to be sorted out in the app:")
        for entry in outcome["sessioni_senza_modulo"]:
            print(f"  - {entry}")
    print("\nNext step: open the app and fill in the email addresses under People.")
