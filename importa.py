"""Importazione iniziale dei dati dall'Excel di partenza.

    python importa.py "/percorso/Piano_formazione_<risorsa>_ISO.xlsx"

Rifiuta di girare se il database contiene gia' dei dati: l'importazione e'
una tantum, e ripeterla creerebbe piani doppi.
"""

import sys
from pathlib import Path

from app import db, importer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    percorso = Path(sys.argv[1]).expanduser()
    if not percorso.exists():
        sys.exit(f"file non trovato: {percorso}")

    conn = db.inizializza()
    if conn.execute("SELECT COUNT(*) c FROM piano").fetchone()["c"]:
        sys.exit(
            f"Il database {db.PERCORSO_DB} contiene gia' dei piani.\n"
            "Cancellalo prima, se vuoi rifare l'importazione da zero."
        )

    esito = importer.importa(percorso, conn)
    print(f"Importato il piano di {esito['risorsa']}:")
    print(f"  {esito['moduli']} moduli, {esito['sessioni']} sessioni, {esito['persone']} persone")
    if esito["sessioni_senza_modulo"]:
        print("\nSessioni senza modulo assegnato, da sistemare nell'app:")
        for voce in esito["sessioni_senza_modulo"]:
            print(f"  - {voce}")
    print("\nProssimo passo: apri l'app e compila gli indirizzi email in «Persone».")
