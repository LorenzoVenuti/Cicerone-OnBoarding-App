"""Esportazione del piano di formazione in PDF, per la stampa e la firma.

Riproduce il modulo del sistema qualita': una pagina in orizzontale con la
testata anagrafica, la tabella dei moduli e lo spazio per la verifica finale e
le firme.

Il codice del modulo stampato in alto a sinistra non e' scritto qui: ogni
azienda ha il suo, e dice di quale azienda si tratta. Si imposta dalla scheda
Piano ISO e vive nell'archivio locale (`db.CHIAVE_CODICE_MODULO`).
"""

import sqlite3
from datetime import date
from pathlib import Path

from fpdf import FPDF

from . import db, regole
from .percorsi import cartella_dati

# larghezza delle colonne in millimetri, su A4 orizzontale (277 mm utili)
COLONNE = [
    ("Cod.", 13), ("Area", 30), ("Formazione / Addestramento", 52),
    ("Appl.", 11), ("Modalita", 24), ("Tutor referente", 32),
    ("Dal", 15), ("Al", 15), ("Sess.", 11), ("Svolte", 12), ("Ore", 11),
    ("Stato", 22), ("Entro il", 15), ("Verifica", 14),
]

GRIGIO_TESTATA = (238, 241, 245)
COLORI_STATO = {
    "Completata": (198, 239, 206),
    "In corso": (189, 215, 238),
    "Da pianificare": (252, 228, 214),
    "N.A.": (217, 217, 217),
}


class Modulo(FPDF):
    def __init__(self, testata: dict, codice_modulo: str):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.testata = testata
        self.codice_modulo = codice_modulo
        self.set_auto_page_break(auto=True, margin=12)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 8)
        self.cell(45, 5, self.codice_modulo, border=1, align="L")
        self.set_font("Helvetica", "B", 10)
        self.cell(187, 5, "SISTEMA DI GESTIONE AMBIENTALE E QUALITA'", border=1, align="C")
        self.set_font("Helvetica", "", 8)
        self.cell(45, 5, f"Pag. {self.page_no()}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_font("Helvetica", "", 8)
        self.cell(45, 5, "Documento del Sistema Qualita'", border=1, align="L")
        self.set_font("Helvetica", "B", 10)
        self.cell(187, 5, "PIANO STANDARD FORMAZIONE RISORSA", border=1, align="C")
        self.cell(45, 5, "", border=1, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)


def _riga_anagrafica(pdf: FPDF, voci: list[tuple[str, str, int]]) -> None:
    for etichetta, valore, larghezza in voci:
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(28, 6, etichetta, border=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(larghezza, 6, valore or "", border=1)
    pdf.ln()


def genera(conn: sqlite3.Connection, piano_id: int, destinazione: Path | None = None) -> Path:
    testata = conn.execute(
        """
        SELECT r.reparto, r.mansione, r.data_inizio, r.motivo,
               pe.nome || ' ' || pe.cognome AS risorsa,
               resp.nome || ' ' || resp.cognome AS responsabile,
               tut.nome  || ' ' || tut.cognome  AS tutor
        FROM piano p JOIN risorsa r ON r.id = p.risorsa_id
        JOIN persona pe ON pe.id = r.persona_id
        LEFT JOIN persona resp ON resp.id = r.responsabile_id
        LEFT JOIN persona tut  ON tut.id  = r.tutor_principale_id
        WHERE p.id = ?
        """,
        (piano_id,),
    ).fetchone()
    if testata is None:
        raise ValueError(f"piano {piano_id} inesistente")

    moduli = regole.riepilogo_moduli(conn, piano_id)

    codice = db.leggi_impostazione(
        conn, db.CHIAVE_CODICE_MODULO, db.CODICE_MODULO_PREDEFINITO
    ) or db.CODICE_MODULO_PREDEFINITO
    pdf = Modulo(dict(testata), codice)
    pdf.add_page()

    motivi = ["Nuova funzione", "Cambio funzione", "Addestramento", "Formazione"]
    scelto = (testata["motivo"] or "").lower()
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(28, 6, "Motivo", border=1)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(249, 6, "      ".join(
        f"{m} {'[X]' if m.lower() == scelto else '[  ]'}" for m in motivi
    ), border=1, new_x="LMARGIN", new_y="NEXT")

    _riga_anagrafica(pdf, [
        ("Nome e Cognome", testata["risorsa"], 77),
        ("Reparto", testata["reparto"], 60),
        ("Mansione", testata["mansione"], 56),
    ])
    _riga_anagrafica(pdf, [
        ("Responsabile", testata["responsabile"], 77),
        ("Tutor", testata["tutor"], 60),
        ("Data inizio", _data_estesa(testata["data_inizio"]), 56),
    ])
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(*GRIGIO_TESTATA)
    for titolo, larghezza in COLONNE:
        pdf.cell(larghezza, 7, titolo, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for m in moduli:
        colore = COLORI_STATO.get(m["stato"])
        valori = [
            m["codice"], m["area"][:24], m["titolo"][:44], m["applicabile"],
            (m["modalita"] or "")[:18], (m["tutor_referente"] or "")[:26],
            _giorno(m["dal"]), _giorno(m["al"]),
            str(m["sessioni_pianificate"]), str(m["sessioni_svolte"]),
            f"{m['ore_svolte']:g}", m["stato"],
            _giorno(m["entro_il"]), m["esito"] or "",
        ]
        for (_, larghezza), valore in zip(COLONNE, valori):
            riempi = colore is not None and valore == m["stato"]
            if riempi:
                pdf.set_fill_color(*colore)
            pdf.cell(larghezza, 4.8, valore, border=1, align="C", fill=riempi)
        pdf.ln()

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*GRIGIO_TESTATA)
    pdf.cell(277, 6, "VERIFICA FINALE", border=1, align="C", fill=True,
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(70, 7, "La risorsa opera in autonomia?", border=1)
    pdf.cell(68, 7, "SI [  ]        NO [  ]", border=1)
    pdf.cell(70, 7, "Sono necessari ulteriori affiancamenti?", border=1)
    pdf.cell(69, 7, "SI [  ]        NO [  ]", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(70, 10, "Osservazioni", border=1)
    pdf.cell(207, 10, "", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    for etichetta in ("Data", "Firma Risorsa", "Firma Tutor", "Firma Responsabile"):
        pdf.cell(69, 8, f"{etichetta}: ______________________", border=0)
    pdf.ln()

    if destinazione is None:
        cartella = cartella_dati() / "dati" / "stampe"
        cartella.mkdir(parents=True, exist_ok=True)
        nome = testata["risorsa"].replace(" ", "_")
        destinazione = cartella / f"Piano_formazione_{nome}_{date.today():%Y%m%d}.pdf"

    pdf.output(str(destinazione))
    return destinazione


def _giorno(iso: str | None) -> str:
    """'2026-09-07' -> '07/09'."""
    return f"{iso[8:10]}/{iso[5:7]}" if iso else ""


def _data_estesa(iso: str | None) -> str:
    """'2026-09-07' -> '07/09/2026'."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else ""
