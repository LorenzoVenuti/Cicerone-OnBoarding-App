"""Regole di calcolo del piano e chiusura automatica delle sessioni.

Direzione unica: le sessioni sono i fatti, tutto il resto e' derivato.
Sostituisce le formule COUNTIFS/MINIFS/SUMIFS del foglio "Piano ISO".
"""

import sqlite3
from datetime import date, datetime, time

ORA_CHIUSURA_AUTOMATICA = time(18, 0)

# Stati che non contano come sessione pianificata (erano i "<>Annullata"
# e "<>Rinviata" delle formule Excel).
STATI_ESCLUSI = ("Annullata", "Rinviata")
STATI_APERTI = ("Pianificata", "Confermata")

COLORI_STATO = {
    "Svolta": "#C6EFCE",
    "Completata": "#C6EFCE",
    "In corso": "#BDD7EE",
    "Rinviata": "#FCE4D6",
    "Da pianificare": "#FCE4D6",
    "Annullata": "#F2DCDB",
    "N.A.": "#D9D9D9",
    "Pianificata": "#FFFFFF",
    "Confermata": "#FFFFFF",
}

# Colore neutro per una sessione senza modulo, o per un'area senza colore.
COLORE_AREA_NEUTRO = "#E9ECF0"

# Dodici tinte pastello ben distinte (giro completo della ruota dei colori):
# fanno da sfondo ai blocchi del calendario e da bordo in agenda, sempre con
# testo scuro sopra, quindi restano leggibili anche col tema scuro. Sono solo un
# punto di partenza: l'utente puo' cambiare il colore di ogni area.
PALETTE_AREE = [
    "#F5C9C9", "#F5DCC0", "#F0EEBE", "#DBEEBE", "#C6EFCE", "#C0EFD6",
    "#BEEFEF", "#C0DCF5", "#C9C9F5", "#DCC0F5", "#F0BEEF", "#F5C0DC",
]


def assicura_colori_aree(conn: sqlite3.Connection) -> None:
    """Garantisce che ogni area abbia un colore. Idempotente.

    Le aree nascono come semplici stringhe sui moduli; qui si assegna un colore
    di default a quelle che ancora non ce l'hanno, riusando la palette a giro.
    Va chiamata all'avvio: cosi' anche un archivio gia' esistente, creato prima
    che le aree avessero un colore, si popola da solo senza migrazioni a mano.
    """
    presenti = {r["nome"] for r in conn.execute("SELECT nome FROM area")}

    aree: list[str] = []
    for riga in conn.execute(
        "SELECT area, MIN(ordine) AS o FROM modulo_catalogo GROUP BY area ORDER BY o"
    ):
        aree.append(riga["area"])
    for riga in conn.execute("SELECT DISTINCT area FROM piano_modulo"):
        if riga["area"] not in aree:
            aree.append(riga["area"])

    nuove = [a for a in aree if a not in presenti]
    if not nuove:
        return
    base = len(presenti)
    conn.executemany(
        "INSERT OR IGNORE INTO area (nome, colore, ordine) VALUES (?, ?, ?)",
        [
            (area, PALETTE_AREE[(base + i) % len(PALETTE_AREE)], base + i)
            for i, area in enumerate(nuove)
        ],
    )
    conn.commit()


def durata_ore(ora_inizio: str, ora_fine: str) -> float:
    """Durata in ore fra due orari 'HH:MM'."""
    inizio = datetime.strptime(ora_inizio, "%H:%M")
    fine = datetime.strptime(ora_fine, "%H:%M")
    return (fine - inizio).total_seconds() / 3600


def stato_modulo(applicabile: str, pianificate: int, svolte: int) -> str:
    if applicabile == "NO":
        return "N.A."
    if pianificate == 0:
        return "Da pianificare"
    if svolte >= pianificate:
        return "Completata"
    if svolte > 0:
        return "In corso"
    return "Pianificata"


def riepilogo_moduli(conn: sqlite3.Connection, piano_id: int) -> list[dict]:
    """Il foglio 'Piano ISO' calcolato: una riga per modulo."""
    moduli = conn.execute(
        """
        SELECT pm.*, p.nome AS tutor_nome, p.cognome AS tutor_cognome
        FROM piano_modulo pm
        LEFT JOIN persona p ON p.id = pm.tutor_referente_id
        WHERE pm.piano_id = ?
        ORDER BY pm.ordine
        """,
        (piano_id,),
    ).fetchall()

    righe = []
    for modulo in moduli:
        sessioni = conn.execute(
            "SELECT data, ora_inizio, ora_fine, stato FROM sessione WHERE piano_modulo_id = ?",
            (modulo["id"],),
        ).fetchall()

        valide = [s for s in sessioni if s["stato"] not in STATI_ESCLUSI]
        svolte = [s for s in valide if s["stato"] == "Svolta"]
        date_valide = sorted(s["data"] for s in valide)

        righe.append(
            {
                "id": modulo["id"],
                "codice": modulo["codice"],
                "area": modulo["area"],
                "titolo": modulo["titolo"],
                "applicabile": modulo["applicabile"],
                "modalita": modulo["modalita"],
                "tutor_referente_id": modulo["tutor_referente_id"],
                "tutor_referente": (
                    f"{modulo['tutor_nome']} {modulo['tutor_cognome']}"
                    if modulo["tutor_nome"]
                    else None
                ),
                "dal": date_valide[0] if date_valide else None,
                "al": date_valide[-1] if date_valide else None,
                "sessioni_pianificate": len(valide),
                "sessioni_svolte": len(svolte),
                "ore_svolte": round(
                    sum(durata_ore(s["ora_inizio"], s["ora_fine"]) for s in svolte), 2
                ),
                "stato": stato_modulo(modulo["applicabile"], len(valide), len(svolte)),
                "entro_il": modulo["entro_il"],
                "verifica_chiusura": modulo["verifica_chiusura"],
                "verifica_efficacia": modulo["verifica_efficacia"],
                "data_verifica": modulo["data_verifica"],
                "esito": modulo["esito"],
            }
        )
    return righe


def sessioni_da_chiudere(conn: sqlite3.Connection, adesso: datetime | None = None) -> list[sqlite3.Row]:
    """Sessioni passate rimaste aperte, che l'auto-completamento deve chiudere.

    Una sessione e' da chiudere se e' ancora aperta, e' passata, e nessuno l'ha
    riprogrammata: se esiste una sessione piu' recente che la sostituisce, quella
    vecchia e' stata rinviata a mano e non ci riguarda.
    """
    adesso = adesso or datetime.now()
    oggi = adesso.date().isoformat()

    candidate = conn.execute(
        f"""
        SELECT * FROM sessione
        WHERE stato IN ({",".join("?" * len(STATI_APERTI))})
          AND data <= ?
        ORDER BY data, ora_inizio
        """,
        (*STATI_APERTI, oggi),
    ).fetchall()

    da_chiudere = []
    for sessione in candidate:
        if sessione["data"] == oggi and adesso.time() < ORA_CHIUSURA_AUTOMATICA:
            continue  # la giornata non e' ancora finita
        sostituita = conn.execute(
            "SELECT 1 FROM sessione WHERE sostituisce_id = ? LIMIT 1", (sessione["id"],)
        ).fetchone()
        if sostituita:
            continue
        da_chiudere.append(sessione)
    return da_chiudere


def chiudi_sessioni_passate(
    conn: sqlite3.Connection, adesso: datetime | None = None
) -> list[sqlite3.Row]:
    """Segna Svolta + esito OK le sessioni passate rimaste aperte.

    Gira all'avvio dell'app, non alle 18:00 in punto: il PC a quell'ora puo'
    essere spento. Le sessioni chiuse restano marcate come automatiche.
    """
    adesso = adesso or datetime.now()
    chiuse = sessioni_da_chiudere(conn, adesso)
    if not chiuse:
        return []

    conn.executemany(
        """
        UPDATE sessione
        SET stato = 'Svolta',
            esito_verifica = COALESCE(NULLIF(esito_verifica, ''), 'OK'),
            chiusa_automaticamente = 1,
            modificata_il = ?
        WHERE id = ?
        """,
        [(adesso.isoformat(timespec="seconds"), s["id"]) for s in chiuse],
    )
    conn.commit()
    return chiuse


def _minuti(ora: str) -> int:
    ore, minuti = ora.split(":")
    return int(ore) * 60 + int(minuti)


def sovrapposizioni(
    conn: sqlite3.Connection,
    piano_id: int,
    data: str,
    ora_inizio: str,
    ora_fine: str,
    tutor: list[int] | None = None,
    escludi_sessione: int | None = None,
) -> list[dict]:
    """Sessioni che si accavallano con quella proposta.

    Due casi impediscono davvero un appuntamento: la risorsa non puo' essere in
    due posti insieme, e nemmeno un tutor, che pero' puo' avere impegni sul
    piano di un'altra risorsa. Le sessioni annullate e rinviate non contano.
    """
    inizio, fine = _minuti(ora_inizio), _minuti(ora_fine)
    tutor = tutor or []

    candidate = conn.execute(
        f"""
        SELECT s.*, pe.nome || ' ' || pe.cognome AS risorsa
        FROM sessione s
        JOIN piano p    ON p.id = s.piano_id
        JOIN risorsa r  ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        WHERE s.data = ?
          AND s.stato NOT IN ({",".join("?" * len(STATI_ESCLUSI))})
          AND (? IS NULL OR s.id != ?)
        """,
        (data, *STATI_ESCLUSI, escludi_sessione, escludi_sessione),
    ).fetchall()

    conflitti = []
    for altra in candidate:
        if _minuti(altra["ora_inizio"]) >= fine or _minuti(altra["ora_fine"]) <= inizio:
            continue

        if altra["piano_id"] == piano_id:
            motivo, chi = "risorsa", altra["risorsa"]
        else:
            tutor_altra = {
                r["persona_id"]
                for r in conn.execute(
                    "SELECT persona_id FROM sessione_tutor WHERE sessione_id = ?",
                    (altra["id"],),
                ).fetchall()
            }
            comuni = tutor_altra & set(tutor)
            if not comuni:
                continue
            nomi = conn.execute(
                f"""SELECT nome || ' ' || cognome AS n FROM persona
                    WHERE id IN ({",".join("?" * len(comuni))})""",
                tuple(comuni),
            ).fetchall()
            motivo, chi = "tutor", ", ".join(r["n"] for r in nomi)

        conflitti.append(
            {
                "sessione_id": altra["id"],
                "motivo": motivo,
                "chi": chi,
                "data": altra["data"],
                "ora_inizio": altra["ora_inizio"],
                "ora_fine": altra["ora_fine"],
                "dettaglio": altra["dettaglio"],
                "risorsa": altra["risorsa"],
            }
        )
    return conflitti
