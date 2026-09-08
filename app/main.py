"""Server locale dell'applicazione."""

import asyncio
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, invio, mail, regole, stampa
from .percorsi import cartella_risorse

CARTELLA_WEB = cartella_risorse() / "app" / "web"

app = FastAPI(title="Piano Formazione")
conn: sqlite3.Connection = db.inizializza()

# Una copia dell'archivio al giorno: e' l'unica copia dei dati che esista.
db.copia_giornaliera()

# Ogni area ha un colore: le aree senza colore lo ricevono qui, all'avvio.
regole.assicura_colori_aree(conn)

# Chiusura automatica: gira all'avvio, non alle 18 in punto, perche' a
# quell'ora il PC puo' essere spento.
_chiuse_all_avvio = [dict(s) for s in regole.chiudi_sessioni_passate(conn)]


class SessioneIn(BaseModel):
    piano_id: int
    piano_modulo_id: int | None = None
    data: str
    ora_inizio: str
    ora_fine: str
    dettaglio: str | None = None
    stato: str = "Pianificata"
    note: str | None = None
    tutor: list[int] = []


class SessionePatch(BaseModel):
    piano_modulo_id: int | None = None
    data: str | None = None
    ora_inizio: str | None = None
    ora_fine: str | None = None
    dettaglio: str | None = None
    stato: str | None = None
    esito_verifica: str | None = None
    note: str | None = None
    tutor: list[int] | None = None


class ModuloPatch(BaseModel):
    applicabile: str | None = None
    modalita: str | None = None
    tutor_referente_id: int | None = None
    entro_il: str | None = None
    verifica_chiusura: str | None = None
    verifica_efficacia: str | None = None
    data_verifica: str | None = None
    esito: str | None = None


class RisorsaIn(BaseModel):
    nome: str
    cognome: str
    email: str | None = None
    reparto: str | None = None
    mansione: str | None = None
    responsabile_id: int | None = None
    tutor_principale_id: int | None = None
    data_inizio: str
    motivo: str = "Nuova funzione"


class ModuloCatalogoIn(BaseModel):
    codice: str
    area: str
    titolo: str
    modalita_default: str | None = None
    tutor_referente_default_id: int | None = None
    colore: str | None = None


class AreaIn(BaseModel):
    nome: str
    colore: str


class PersonaIn(BaseModel):
    nome: str
    cognome: str
    email: str | None = None
    reparto: str | None = None


class ImpostazioneMailIn(BaseModel):
    invio_email_automatico: bool


class CanaleMailIn(BaseModel):
    canale: str
    mittente: str | None = None


class CodiceModuloIn(BaseModel):
    codice: str


class ProvaMailIn(BaseModel):
    destinatario: str
    canale: str | None = None
    mittente: str | None = None


def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sessioni_del_piano(piano_id: int) -> list[dict]:
    righe = conn.execute(
        """
        SELECT s.*, pm.codice, pm.titolo AS modulo_titolo, pm.area,
               a.colore AS colore_area
        FROM sessione s
        LEFT JOIN piano_modulo pm ON pm.id = s.piano_modulo_id
        LEFT JOIN area a ON a.nome = pm.area
        WHERE s.piano_id = ?
        ORDER BY s.data, s.ora_inizio
        """,
        (piano_id,),
    ).fetchall()

    tutor_per_sessione: dict[int, list[dict]] = {}
    for riga in conn.execute(
        """
        SELECT st.sessione_id, p.id, p.nome, p.cognome, p.email
        FROM sessione_tutor st JOIN persona p ON p.id = st.persona_id
        JOIN sessione s ON s.id = st.sessione_id
        WHERE s.piano_id = ?
        """,
        (piano_id,),
    ).fetchall():
        tutor_per_sessione.setdefault(riga["sessione_id"], []).append(
            {"id": riga["id"], "nome": f"{riga['nome']} {riga['cognome']}", "email": riga["email"]}
        )

    sessioni = []
    for riga in righe:
        voce = dict(riga)
        voce["tutor"] = tutor_per_sessione.get(riga["id"], [])
        voce["durata"] = regole.durata_ore(riga["ora_inizio"], riga["ora_fine"])
        voce["colore"] = regole.COLORI_STATO.get(riga["stato"], "#FFFFFF")
        voce["colore_area"] = riga["colore_area"] or regole.COLORE_AREA_NEUTRO
        sessioni.append(voce)
    return sessioni


def _imposta_tutor(sessione_id: int, tutor: list[int]) -> None:
    conn.execute("DELETE FROM sessione_tutor WHERE sessione_id = ?", (sessione_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO sessione_tutor (sessione_id, persona_id) VALUES (?, ?)",
        [(sessione_id, t) for t in tutor],
    )


def _upsert_area(nome: str, colore: str) -> None:
    """Fissa il colore di un'area, creandola se non esiste ancora."""
    conn.execute(
        """
        INSERT INTO area (nome, colore, ordine)
        VALUES (?, ?, COALESCE((SELECT MAX(ordine) + 1 FROM area), 0))
        ON CONFLICT(nome) DO UPDATE SET colore = excluded.colore
        """,
        (nome, colore),
    )


async def _notifica(sessione_id: int, tipo: str, precedente: dict | None = None) -> dict:
    messaggio = mail.componi(
        conn, sessione_id, tipo, precedente=precedente,
        # chi organizza l'appuntamento e' l'indirizzo scelto in configurazione
        organizzatore=db.leggi_impostazione(conn, db.CHIAVE_MITTENTE_MAIL),
    )
    esito = await invio.invia_senza_bloccare(conn, messaggio)
    return {"oggetto": messaggio["oggetto"], **esito}


@app.get("/api/stato")
async def stato():
    piani = conn.execute(
        """
        SELECT p.id, p.creato_il, r.reparto, r.mansione, r.data_inizio,
               pe.nome || ' ' || pe.cognome AS risorsa
        FROM piano p JOIN risorsa r ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        ORDER BY r.data_inizio DESC
        """
    ).fetchall()
    senza_email = conn.execute(
        "SELECT COUNT(*) c FROM persona WHERE email IS NULL OR email = ''"
    ).fetchone()["c"]
    return {
        "piani": [dict(p) for p in piani],
        "chiuse_all_avvio": _chiuse_all_avvio,
        "persone_senza_email": senza_email,
        "canale_mail": invio.scegli_canale(conn).nome,
        "invio_email_automatico": db.invio_email_automatico(conn),
        # Finche' e' falso l'app non sa da dove spedire: l'interfaccia lo chiede.
        "mail_configurata": bool(db.leggi_impostazione(conn, db.CHIAVE_CANALE_MAIL)),
        "mittente_mail": db.leggi_impostazione(conn, db.CHIAVE_MITTENTE_MAIL),
        "codice_modulo": db.leggi_impostazione(
            conn, db.CHIAVE_CODICE_MODULO, db.CODICE_MODULO_PREDEFINITO
        ),
    }


@app.get("/api/piano/{piano_id}")
async def piano(piano_id: int):
    testata = conn.execute(
        """
        SELECT p.id, r.reparto, r.mansione, r.data_inizio, r.motivo,
               pe.nome || ' ' || pe.cognome AS risorsa,
               resp.nome || ' ' || resp.cognome AS responsabile,
               tut.nome  || ' ' || tut.cognome  AS tutor_principale
        FROM piano p JOIN risorsa r ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        LEFT JOIN persona resp ON resp.id = r.responsabile_id
        LEFT JOIN persona tut  ON tut.id  = r.tutor_principale_id
        WHERE p.id = ?
        """,
        (piano_id,),
    ).fetchone()
    if testata is None:
        raise HTTPException(404, "piano inesistente")

    colori_area = {
        r["nome"]: r["colore"] for r in conn.execute("SELECT nome, colore FROM area")
    }
    moduli = regole.riepilogo_moduli(conn, piano_id)
    for modulo in moduli:
        modulo["colore"] = regole.COLORI_STATO.get(modulo["stato"], "#FFFFFF")
        modulo["colore_area"] = colori_area.get(modulo["area"], regole.COLORE_AREA_NEUTRO)
    return {
        "testata": dict(testata),
        "moduli": moduli,
        "sessioni": _sessioni_del_piano(piano_id),
    }


@app.post("/api/risorse")
async def crea_risorsa(dati: RisorsaIn):
    """Crea la persona, la risorsa e il suo piano, copiando i moduli dal catalogo.

    E' l'unico modo per far partire un percorso senza passare da un Excel e da
    Python, che sul computer di chi usa il programma non ci sono.
    """
    adesso = _adesso()
    persona = conn.execute(
        "SELECT id FROM persona WHERE nome = ? AND cognome = ?",
        (dati.nome, dati.cognome),
    ).fetchone()
    if persona:
        persona_id = persona["id"]
        if dati.email:
            conn.execute("UPDATE persona SET email = ? WHERE id = ?", (dati.email, persona_id))
    else:
        persona_id = conn.execute(
            "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)",
            (dati.nome, dati.cognome, dati.email, dati.reparto),
        ).lastrowid

    risorsa_id = conn.execute(
        """
        INSERT INTO risorsa (persona_id, reparto, mansione, responsabile_id,
                             tutor_principale_id, data_inizio, motivo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (persona_id, dati.reparto, dati.mansione, dati.responsabile_id,
         dati.tutor_principale_id, dati.data_inizio, dati.motivo),
    ).lastrowid

    piano_id = conn.execute(
        "INSERT INTO piano (risorsa_id, creato_il) VALUES (?, ?)", (risorsa_id, adesso)
    ).lastrowid

    catalogo = conn.execute("SELECT * FROM modulo_catalogo ORDER BY ordine").fetchall()
    for modulo in catalogo:
        conn.execute(
            """
            INSERT INTO piano_modulo
                (piano_id, codice, area, titolo, applicabile, modalita,
                 tutor_referente_id, ordine)
            VALUES (?, ?, ?, ?, 'SI', ?, ?, ?)
            """,
            (piano_id, modulo["codice"], modulo["area"], modulo["titolo"],
             modulo["modalita_default"], modulo["tutor_referente_default_id"],
             modulo["ordine"]),
        )
    conn.commit()
    return {"piano_id": piano_id, "risorsa_id": risorsa_id, "moduli": len(catalogo)}


@app.get("/api/catalogo")
async def catalogo():
    righe = conn.execute(
        """
        SELECT c.*, p.nome || ' ' || p.cognome AS tutor,
               a.colore AS colore,
               (SELECT COUNT(*) FROM piano_modulo pm WHERE pm.codice = c.codice) AS usato_in
        FROM modulo_catalogo c
        LEFT JOIN persona p ON p.id = c.tutor_referente_default_id
        LEFT JOIN area a ON a.nome = c.area
        ORDER BY c.ordine
        """
    ).fetchall()
    return [dict(r) for r in righe]


@app.post("/api/catalogo")
async def crea_modulo_catalogo(dati: ModuloCatalogoIn):
    esistente = conn.execute(
        "SELECT 1 FROM modulo_catalogo WHERE codice = ?", (dati.codice,)
    ).fetchone()
    if esistente:
        raise HTTPException(400, f"il codice {dati.codice} esiste gia'")
    ordine = conn.execute(
        "SELECT COALESCE(MAX(ordine), 0) + 1 AS o FROM modulo_catalogo"
    ).fetchone()["o"]
    conn.execute(
        """
        INSERT INTO modulo_catalogo
            (codice, area, titolo, modalita_default, tutor_referente_default_id, ordine)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (dati.codice, dati.area, dati.titolo, dati.modalita_default,
         dati.tutor_referente_default_id, ordine),
    )
    if dati.colore:
        _upsert_area(dati.area, dati.colore)
    else:
        regole.assicura_colori_aree(conn)  # area nuova senza colore: default
    conn.commit()
    return {"codice": dati.codice}


@app.patch("/api/catalogo/{codice}")
async def modifica_modulo_catalogo(codice: str, dati: ModuloCatalogoIn):
    conn.execute(
        """
        UPDATE modulo_catalogo
        SET area = ?, titolo = ?, modalita_default = ?, tutor_referente_default_id = ?
        WHERE codice = ?
        """,
        (dati.area, dati.titolo, dati.modalita_default,
         dati.tutor_referente_default_id, codice),
    )
    if dati.colore:
        _upsert_area(dati.area, dati.colore)
    else:
        regole.assicura_colori_aree(conn)
    conn.commit()
    return {"codice": codice}


@app.delete("/api/catalogo/{codice}")
async def elimina_modulo_catalogo(codice: str):
    """Toglie un modulo dal catalogo. I piani gia' creati non cambiano."""
    conn.execute("DELETE FROM modulo_catalogo WHERE codice = ?", (codice,))
    conn.commit()
    return {"codice": codice}


@app.get("/api/aree")
async def aree():
    """Aree formative con il loro colore, per la legenda e per l'editor."""
    righe = conn.execute(
        "SELECT nome, colore, ordine FROM area ORDER BY ordine, nome"
    ).fetchall()
    return [dict(r) for r in righe]


@app.put("/api/aree")
async def salva_area(dati: AreaIn):
    """Cambia il colore di un'area: si riflette su tutti i suoi moduli."""
    _upsert_area(dati.nome, dati.colore)
    conn.commit()
    return {"nome": dati.nome, "colore": dati.colore}


@app.put("/api/documento/codice")
async def salva_codice_modulo(dati: CodiceModuloIn):
    """Il codice del modulo stampato in testa al PDF.

    Ogni azienda ha il suo, preso dal proprio sistema qualita': sta
    nell'archivio e non nel codice.
    """
    db.salva_impostazione(conn, db.CHIAVE_CODICE_MODULO, dati.codice.strip())
    return {"codice": dati.codice.strip()}


@app.post("/api/piano/{piano_id}/stampa")
async def stampa_piano(piano_id: int):
    """Genera il PDF del modulo ISO e lo apre col visualizzatore di sistema."""
    percorso = stampa.genera(conn, piano_id)
    try:
        if sys.platform == "win32":
            os.startfile(percorso)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(percorso)])
        else:
            subprocess.Popen(["xdg-open", str(percorso)])
    except Exception:
        pass  # il file resta comunque salvato, il percorso e' nella risposta
    return {"percorso": str(percorso)}


@app.get("/api/conflitti")
async def conflitti(
    piano_id: int, data: str, ora_inizio: str, ora_fine: str,
    tutor: str = "", escludi: int | None = None,
):
    """Sessioni che si accavallano con quella proposta."""
    elenco = [int(t) for t in tutor.split(",") if t.strip()]
    return regole.sovrapposizioni(
        conn, piano_id, data, ora_inizio, ora_fine, elenco, escludi
    )


@app.post("/api/sessioni")
async def crea_sessione(dati: SessioneIn):
    adesso = _adesso()
    sessione_id = conn.execute(
        """
        INSERT INTO sessione (piano_id, piano_modulo_id, data, ora_inizio, ora_fine,
                              dettaglio, stato, note, creata_il, modificata_il)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (dati.piano_id, dati.piano_modulo_id, dati.data, dati.ora_inizio, dati.ora_fine,
         dati.dettaglio, dati.stato, dati.note, adesso, adesso),
    ).lastrowid
    _imposta_tutor(sessione_id, dati.tutor)
    conn.commit()
    return {"id": sessione_id, "mail": await _notifica(sessione_id, "nuova")}


@app.patch("/api/sessioni/{sessione_id}")
async def modifica_sessione(sessione_id: int, dati: SessionePatch):
    prima = conn.execute("SELECT * FROM sessione WHERE id = ?", (sessione_id,)).fetchone()
    if prima is None:
        raise HTTPException(404, "sessione inesistente")

    campi = dati.model_dump(exclude_none=True)
    tutor = campi.pop("tutor", None)

    if campi:
        assegnazioni = ", ".join(f"{c} = ?" for c in campi)
        conn.execute(
            f"UPDATE sessione SET {assegnazioni}, modificata_il = ? WHERE id = ?",
            (*campi.values(), _adesso(), sessione_id),
        )
    if tutor is not None:
        _imposta_tutor(sessione_id, tutor)
    conn.commit()

    # Una modifica esplicita esce dal regime automatico.
    if campi.get("stato") or campi.get("esito_verifica"):
        conn.execute(
            "UPDATE sessione SET chiusa_automaticamente = 0 WHERE id = ?", (sessione_id,)
        )
        conn.commit()

    spostata = any(
        campi.get(c) is not None and campi[c] != prima[c]
        for c in ("data", "ora_inizio", "ora_fine")
    )
    risposta = {"id": sessione_id, "spostata": spostata}
    if spostata:
        risposta["mail"] = await _notifica(
            sessione_id,
            "spostamento",
            precedente={
                "data": prima["data"],
                "ora_inizio": prima["ora_inizio"],
                "ora_fine": prima["ora_fine"],
            },
        )
    elif campi.get("stato") == "Annullata":
        risposta["mail"] = await _notifica(sessione_id, "annullamento")
    return risposta


@app.delete("/api/sessioni/{sessione_id}")
async def annulla_sessione(sessione_id: int):
    """Le sessioni non si cancellano: si annullano, e restano nel piano."""
    conn.execute(
        "UPDATE sessione SET stato = 'Annullata', modificata_il = ? WHERE id = ?",
        (_adesso(), sessione_id),
    )
    conn.commit()
    return {"id": sessione_id, "mail": await _notifica(sessione_id, "annullamento")}


@app.patch("/api/moduli/{modulo_id}")
async def modifica_modulo(modulo_id: int, dati: ModuloPatch):
    campi = dati.model_dump(exclude_unset=True)
    if not campi:
        return {"id": modulo_id}
    assegnazioni = ", ".join(f"{c} = ?" for c in campi)
    conn.execute(
        f"UPDATE piano_modulo SET {assegnazioni} WHERE id = ?", (*campi.values(), modulo_id)
    )
    conn.commit()
    return {"id": modulo_id}


@app.get("/api/persone")
async def persone():
    righe = conn.execute(
        """
        SELECT p.*, EXISTS (SELECT 1 FROM risorsa r WHERE r.persona_id = p.id) AS e_risorsa
        FROM persona p WHERE p.attivo = 1 ORDER BY p.cognome, p.nome
        """
    ).fetchall()
    return [dict(r) for r in righe]


@app.patch("/api/persone/{persona_id}")
async def modifica_persona(persona_id: int, dati: PersonaIn):
    conn.execute(
        "UPDATE persona SET nome = ?, cognome = ?, email = ?, reparto = ? WHERE id = ?",
        (dati.nome, dati.cognome, dati.email, dati.reparto, persona_id),
    )
    conn.commit()
    return {"id": persona_id}


@app.post("/api/persone")
async def crea_persona(dati: PersonaIn):
    cursore = conn.execute(
        "INSERT INTO persona (nome, cognome, email, reparto) VALUES (?, ?, ?, ?)",
        (dati.nome, dati.cognome, dati.email, dati.reparto),
    )
    conn.commit()
    return {"id": cursore.lastrowid}


@app.get("/api/mail")
async def registro_mail():
    righe = conn.execute(
        """
        SELECT m.*, s.data AS sessione_data
        FROM mail_log m LEFT JOIN sessione s ON s.id = m.sessione_id
        ORDER BY m.id DESC LIMIT 200
        """
    ).fetchall()
    return [mail.voce_log(r) for r in righe]


@app.get("/api/mail/impostazioni")
async def impostazioni_mail():
    """Restituisce lo stato persistente della consegna automatica."""
    return {"invio_email_automatico": db.invio_email_automatico(conn)}


@app.put("/api/mail/impostazioni")
async def salva_impostazioni_mail(dati: ImpostazioneMailIn):
    """Abilita o disabilita la consegna reale delle notifiche."""
    db.salva_impostazione(
        conn,
        db.CHIAVE_INVIO_EMAIL_AUTOMATICO,
        "1" if dati.invio_email_automatico else "0",
    )
    return {"invio_email_automatico": dati.invio_email_automatico}


@app.get("/api/mail/canali")
async def canali_mail():
    """I programmi di posta presenti su questo computer, con i loro account.

    Interroga davvero i programmi, quindi puo' avviarli: e' accettabile qui,
    perche' viene chiamata dalla schermata di configurazione, non a ogni pagina.
    """
    trovati = await asyncio.to_thread(invio.diagnosi_canali)
    return {
        "canali": trovati,
        "scelto": db.leggi_impostazione(conn, db.CHIAVE_CANALE_MAIL),
        "mittente": db.leggi_impostazione(conn, db.CHIAVE_MITTENTE_MAIL),
    }


@app.put("/api/mail/canale")
async def salva_canale_mail(dati: CanaleMailIn):
    """Registra da dove partiranno le notifiche su questo computer."""
    if invio.canale_per_nome(dati.canale) is None:
        raise HTTPException(400, f"canale sconosciuto: {dati.canale}")
    db.salva_impostazione(conn, db.CHIAVE_CANALE_MAIL, dati.canale)
    db.salva_impostazione(conn, db.CHIAVE_MITTENTE_MAIL, dati.mittente or "")
    return {"canale": dati.canale, "mittente": dati.mittente or ""}


@app.post("/api/mail/prova")
async def prova_mail(dati: ProvaMailIn):
    """Manda una mail di prova e riporta cosa e' successo davvero.

    Non passa dalla policy di invio automatico: serve proprio a verificare che
    il canale funzioni *prima* di accenderla. Non entra nel registro delle
    notifiche, che documenta la formazione e non le prove tecniche.

    Gira in un thread perche' aspetta che il programma di posta tolga il
    messaggio dalla coda: nell'event loop bloccherebbe tutta l'applicazione.
    """
    if dati.canale:
        canale = invio.canale_per_nome(dati.canale, dati.mittente)
        if canale is None:
            raise HTTPException(400, f"canale sconosciuto: {dati.canale}")
    else:
        canale = invio.scegli_canale(conn)

    messaggio = {
        "tipo": "prova",
        "sessione_id": 0,
        "oggetto": "Piano Formazione: prova di invio",
        "corpo": (
            "Questa e' una prova dell'invio automatico del Piano Formazione.\n\n"
            "Se la stai leggendo, le notifiche di creazione, spostamento e "
            "annullamento delle sessioni possono partire da questo computer.\n"
        ),
        "destinatari": [dati.destinatario.strip()],
        "senza_email": [],
    }
    try:
        await asyncio.to_thread(canale.invia, messaggio)
    except Exception as errore:
        return {"esito": "errore", "canale": canale.nome, "errore": str(errore)}
    return {"esito": "inviata", "canale": canale.nome}


@app.post("/api/mail/riprova-tutte")
async def riprova_tutte_le_mail():
    """Riprova le notifiche bloccate o fallite, dalla piu' vecchia.

    Serve dopo aver acceso l'invio o sistemato il programma di posta: le
    notifiche restate indietro partono senza doverle riprendere una per una.
    """
    righe = conn.execute(
        """
        SELECT * FROM mail_log
        WHERE esito IN ('invio_disattivato', 'errore')
        ORDER BY id
        """
    ).fetchall()

    riepilogo = {"totale": len(righe), "inviate": 0, "errori": 0, "bloccate": 0}
    for riga in righe:
        esito = await invio.invia_senza_bloccare(
            conn, mail.messaggio_da_log(riga), mail_log_id=riga["id"]
        )
        if esito["esito"] == "inviata":
            riepilogo["inviate"] += 1
        elif esito["esito"] == "errore":
            riepilogo["errori"] += 1
        else:
            riepilogo["bloccate"] += 1
    return riepilogo


@app.post("/api/mail/{mail_id}/riprova")
async def riprova_mail(mail_id: int):
    """Riprova una consegna senza ricreare una nuova voce nel log."""
    riga = conn.execute(
        "SELECT * FROM mail_log WHERE id = ?", (mail_id,)
    ).fetchone()
    if riga is None:
        raise HTTPException(404, "voce mail inesistente")
    if riga["esito"] not in {"invio_disattivato", "errore"}:
        raise HTTPException(409, "questa mail non è riprovabile")
    messaggio = mail.messaggio_da_log(riga)
    return {"id": mail_id, **await invio.invia_senza_bloccare(conn, messaggio, mail_log_id=mail_id)}


@app.delete("/api/mail/{mail_id}")
async def elimina_mail(mail_id: int):
    """Elimina esclusivamente una voce dal registro delle email."""
    cursore = conn.execute("DELETE FROM mail_log WHERE id = ?", (mail_id,))
    if cursore.rowcount == 0:
        raise HTTPException(404, "voce mail inesistente")
    conn.commit()
    return {"id": mail_id}


@app.middleware("http")
async def niente_cache(richiesta, prosegui):
    """L'interfaccia non va mai in cache.

    Server e pagina si aggiornano insieme: un JavaScript vecchio rimasto in
    cache contro un HTML nuovo produce errori che sembrano bug dell'app.
    """
    risposta = await prosegui(richiesta)
    risposta.headers["Cache-Control"] = "no-store"
    return risposta


@app.get("/")
async def home():
    return FileResponse(CARTELLA_WEB / "index.html")


app.mount("/statico", StaticFiles(directory=CARTELLA_WEB), name="statico")
