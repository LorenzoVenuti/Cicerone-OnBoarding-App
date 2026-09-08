"""Popola un archivio di prova con dati inventati.

Serve per sviluppare e verificare l'app senza usare i dati veri, che non fanno
parte del repository. Struttura identica a quella reale: una risorsa, 21 moduli,
sessioni su cinque settimane, sessioni gia' svolte e altre da fare.

    python semina_esempio.py            # crea dati/piano.db
    python semina_esempio.py prova.db   # crea un archivio altrove
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app import db

PERSONE = [
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

# Catalogo di esempio: un percorso di inserimento come lo avrebbe una qualsiasi
# azienda manifatturiera. E' deliberatamente generico. Il catalogo vero di
# un'azienda dice cosa produce e com'e' organizzata dentro, quindi non sta nel
# codice: si carica da `importa.py` oppure si scrive dalla scheda Moduli, e vive
# solo nell'archivio locale.
MODULI = [
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

# (giorni dall'inizio, inizio, fine, indice modulo, dettaglio, indici tutor)
SESSIONI = [
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


def semina(percorso: Path) -> None:
    conn = db.inizializza(percorso)
    if conn.execute("SELECT COUNT(*) c FROM piano").fetchone()["c"]:
        sys.exit(f"{percorso} contiene gia' dei dati: cancellalo prima.")

    adesso = datetime.now().isoformat(timespec="seconds")
    # L'inizio e' due settimane fa, cosi' alcune sessioni risultano gia' passate
    # e la chiusura automatica ha qualcosa su cui lavorare.
    inizio = date.today() - timedelta(days=14)

    persone = [
        conn.execute(
            "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)", p
        ).lastrowid
        for p in PERSONE
    ]
    risorsa_persona = conn.execute(
        "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)",
        ("Andrea", "Neri", "andrea.neri@esempio.test", "Vendite"),
    ).lastrowid

    risorsa_id = conn.execute(
        """
        INSERT INTO risorsa (persona_id, reparto, mansione, responsabile_id,
                             tutor_principale_id, data_inizio, motivo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (risorsa_persona, "Vendite", "Tecnico commerciale", persone[0], persone[8],
         inizio.isoformat(), "Nuova funzione"),
    ).lastrowid
    piano_id = conn.execute(
        "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, ?)", (risorsa_id, adesso)
    ).lastrowid

    moduli = []
    for ordine, (codice, area, titolo, modalita) in enumerate(MODULI, start=1):
        tutor = persone[ordine % len(persone)]
        conn.execute(
            """
            INSERT INTO modulo_catalogo
                (codice, area, titolo, modalita_default, tutor_referente_default_id, ordine)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (codice, area, titolo, modalita, tutor, ordine),
        )
        moduli.append(
            conn.execute(
                """
                INSERT INTO piano_modulo
                    (piano_id, codice, area, titolo, applicabile, modalita,
                     tutor_referente_id, ordine)
                VALUES (?, ?, ?, ?, 'SI', ?, ?, ?)
                """,
                (piano_id, codice, area, titolo, modalita, tutor, ordine),
            ).lastrowid
        )

    oggi = date.today()
    for scarto, ora_inizio, ora_fine, indice_modulo, dettaglio, indici_tutor in SESSIONI:
        giorno = inizio + timedelta(days=scarto)
        stato = "Svolta" if giorno < oggi - timedelta(days=1) else "Pianificata"
        sessione_id = conn.execute(
            """
            INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio, ora_fine,
                                  dettaglio, stato, esito_verifica, creata_il, modificata_il)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (piano_id, moduli[indice_modulo] if indice_modulo is not None else None,
             giorno.isoformat(), ora_inizio, ora_fine, dettaglio, stato,
             "OK" if stato == "Svolta" else None, adesso, adesso),
        ).lastrowid
        for indice in indici_tutor:
            conn.execute(
                "INSERT INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
                (sessione_id, persone[indice]),
            )

    conn.commit()
    print(f"Creato {percorso}")
    print(f"  1 risorsa, {len(MODULI)} moduli, {len(SESSIONI)} sessioni, {len(PERSONE) + 1} persone")
    print("  due persone sono volutamente senza email, per provare l'avviso")


if __name__ == "__main__":
    semina(Path(sys.argv[1]) if len(sys.argv) > 1 else db.PERCORSO_DB)
