"""Fills a demo archive with invented data.

It exists so the app can be developed and checked without the real data, which
is not part of this repository. Same shape as a real archive: one trainee, 21
modules, sessions spread over five weeks, some already held and some still to
come. Two people are deliberately left without an email address, so the warning
the app shows can be verified.

The data itself stays in Italian, like the interface: it is what a user would
actually see on screen.

    python seed_demo.py            # creates dati/piano.db
    python seed_demo.py demo.db    # creates an archive elsewhere
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app import db

PEOPLE = [
    ("Giulia", "Bianchi", "giulia.bianchi@esempio.test", "Vendite"),
    ("Marco", "Ferrari", "marco.ferrari@esempio.test", "Amministrazione"),
    ("Elena", "Ricci", "elena.ricci@esempio.test", "Marketing"),
    ("Davide", "Costa", "davide.costa@esempio.test", "Produzione"),
    ("Sara", "Greco", "sara.greco@esempio.test", "Qualita'"),
    ("Luca", "Moretti", "luca.moretti@esempio.test", "Ufficio Tecnico"),
    ("Chiara", "Barbieri", None, "Ufficio Tecnico"),
    ("Alessio", "Fontana", "alessio.fontana@esempio.test", "Acquisti"),
    ("Martina", "Serra", "martina.serra@esempio.test", "Customer care"),
    ("Paolo", "Villa", None, "IT"),
]

# A sample catalogue: an induction path as any manufacturing company might run
# it. It is deliberately generic. A real catalogue says what a company makes and
# how it is organised inside, so it does not belong in the code: it is loaded
# with `import_spreadsheet.py` or typed in from the Modules tab, and lives only
# in the local archive.
CATALOGUE = [
    ("M01", "Generale", "Presentazione azienda", "Spiegazione"),
    ("M02", "Amministrazione", "Dotazioni e adempimenti", "Spiegazione"),
    ("M03", "Sicurezza", "Sicurezza sul lavoro", "Spiegazione"),
    ("M04", "Generale", "Codice etico e condotta", "Autoapprendimento"),
    ("M05", "Sistemi di gestione", "Qualita' e ambiente", "Spiegazione"),
    ("M06", "IT", "Strumenti e gestionali", "Spiegazione"),
    ("M07", "Marketing", "Sito web e materiali", "Spiegazione"),
    ("M08", "Produzione", "Produzione e logistica", "Spiegazione"),
    ("M09", "Acquisti", "Ciclo passivo", "Spiegazione"),
    ("M10", "Vendite", "Ciclo attivo e assistenza", "Spiegazione"),
    ("M11", "Commerciale", "Portafoglio clienti", "Affiancamento"),
    ("M12", "Commerciale", "Mercati esteri", "Spiegazione"),
    ("M13", "Commerciale", "Listino e condizioni di vendita", "Spiegazione"),
    ("M14", "Ufficio Tecnico", "Catalogo e codifica articoli", "Spiegazione"),
    ("M15", "Ufficio Tecnico", "Distinta base e disegni", "Spiegazione"),
    ("M16", "Ufficio Tecnico", "Strumenti di progettazione", "Spiegazione"),
    ("M17", "Ufficio Tecnico", "Materiali e componenti", "Spiegazione"),
    ("M18", "Ufficio Tecnico", "Normative e marcature", "Spiegazione"),
    ("M19", "Ufficio Tecnico", "Laboratorio e prove", "Affiancamento"),
    ("M20", "Ufficio Tecnico", "Collaudo e non conformita'", "Spiegazione"),
    ("M21", "Customer care", "Assistenza pre e post vendita", "Spiegazione"),
]

# (days from the start, start, end, module index, detail, tutor indexes)
SESSIONS = [
    (0, "08:30", "09:00", 0,  "Benvenuto e presentazione", [0, 1]),
    (0, "09:00", "10:00", 1,  "Dotazioni e documenti", [1]),
    (0, "10:00", "12:30", 0,  "Storia e mercati dell'azienda", [0]),
    (0, "13:30", "17:30", 10, "Portafoglio clienti - prima parte", [0, 8]),
    (1, "09:00", "10:30", 6,  "Catalogo e materiali", [2]),
    (1, "10:30", "12:30", 10, "Portafoglio clienti - seconda parte", [8]),
    (1, "14:00", "17:30", 19, "Collaudo e non conformita' - prima parte", [5]),
    (4, "08:30", "10:00", 9,  "Ciclo attivo", [8]),
    (4, "10:00", "11:30", 17, "Normative e marcature - prima parte", [6]),
    (4, "14:00", "17:00", 18, "Laboratorio - prima parte", [5]),
    (5, "09:00", "10:00", 4,  "Sistema qualita'", [4]),
    (5, "10:00", "12:30", 13, "Catalogo tecnico", [6]),
    (5, "14:00", "17:30", 19, "Collaudo e non conformita' - seconda parte", [5]),
    (6, "08:30", "17:30", 10, "Visite clienti", [8]),
    (7, "09:00", "12:00", 8,  "Ciclo passivo", [7]),
    (7, "14:00", "17:30", 10, "Rientro e inserimento a sistema", [8]),
    (11, "08:30", "10:30", None, "Da assegnare", []),
    (11, "14:00", "15:30", 15, "Strumenti di progettazione", [6]),
    (11, "15:30", "17:30", 18, "Laboratorio - seconda parte", [5]),
    (13, "09:00", "11:30", 10, "Rientro e inserimento a sistema", [8]),
    (13, "14:00", "15:30", 16, "Materiali e componenti", [5]),
    (13, "15:30", "17:30", 20, "Assistenza tecnica", [8]),
    (18, "09:00", "11:00", 7,  "Produzione e logistica", [3]),
    (18, "14:00", "17:30", 6,  "Sito web e strumenti digitali", [2]),
    (19, "08:30", "10:30", 13, "Approfondimento catalogo", [6]),
    (19, "13:30", "17:30", 17, "Normative e marcature - seconda parte", [6]),
    (25, "09:00", "17:30", 12, "Giornata in affiancamento commerciale", [3]),
    (32, "14:00", "17:30", None, "Ripasso generale", [5]),
]


def seed(path: Path) -> None:
    conn = db.initialise(path)
    if conn.execute("SELECT COUNT(*) c FROM piano").fetchone()["c"]:
        sys.exit(f"{path} already holds data: delete it first.")

    now = datetime.now().isoformat(timespec="seconds")
    # The start is two weeks ago, so some sessions are already in the past and
    # automatic closing has something to work on.
    start = date.today() - timedelta(days=14)

    people = [
        conn.execute(
            "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)", p
        ).lastrowid
        for p in PEOPLE
    ]
    trainee_person = conn.execute(
        "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)",
        ("Andrea", "Neri", "andrea.neri@esempio.test", "Vendite"),
    ).lastrowid

    trainee_id = conn.execute(
        """
        INSERT INTO risorsa (persona_id, reparto, mansione, responsabile_id,
                             tutor_principale_id, data_inizio, motivo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (trainee_person, "Vendite", "Tecnico commerciale", people[0], people[8],
         start.isoformat(), "Nuova funzione"),
    ).lastrowid
    plan_id = conn.execute(
        "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, ?)", (trainee_id, now)
    ).lastrowid

    modules = []
    for order, (codice, area, titolo, modalita) in enumerate(CATALOGUE, start=1):
        tutor = people[order % len(people)]
        conn.execute(
            """
            INSERT INTO modulo_catalogo
                (codice, area, titolo, modalita_default, tutor_referente_default_id, ordine)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (codice, area, titolo, modalita, tutor, order),
        )
        modules.append(
            conn.execute(
                """
                INSERT INTO piano_modulo
                    (piano_id, codice, area, titolo, applicabile, modalita,
                     tutor_referente_id, ordine)
                VALUES (?, ?, ?, ?, 'SI', ?, ?, ?)
                """,
                (plan_id, codice, area, titolo, modalita, tutor, order),
            ).lastrowid
        )

    today = date.today()
    for offset, ora_inizio, ora_fine, module_index, dettaglio, tutor_indexes in SESSIONS:
        day = start + timedelta(days=offset)
        stato = "Svolta" if day < today - timedelta(days=1) else "Pianificata"
        session_id = conn.execute(
            """
            INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio, ora_fine,
                                  dettaglio, stato, esito_verifica, creata_il, modificata_il)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (plan_id, modules[module_index] if module_index is not None else None,
             day.isoformat(), ora_inizio, ora_fine, dettaglio, stato,
             "OK" if stato == "Svolta" else None, now, now),
        ).lastrowid
        for index in tutor_indexes:
            conn.execute(
                "INSERT INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
                (session_id, people[index]),
            )

    conn.commit()
    print(f"Created {path}")
    print(f"  1 trainee, {len(CATALOGUE)} modules, {len(SESSIONS)} sessions, {len(PEOPLE) + 1} people")
    print("  two people are deliberately left without an email, to exercise the warning")


if __name__ == "__main__":
    seed(Path(sys.argv[1]) if len(sys.argv) > 1 else db.DB_PATH)
