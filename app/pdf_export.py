"""Exporting the training plan to PDF, for printing and signing.

Reproduces the quality-system form: one landscape page with the header details,
the table of modules and room for the final assessment and the signatures.

The form code printed top left is not written here: every company has its own,
and it identifies the company. It is set from the training plan tab and lives in
the local archive (`db.KEY_FORM_CODE`).

The printed labels stay in Italian: the sheet is signed by Italian readers and
filed as a certification record.
"""

import sqlite3
from datetime import date
from pathlib import Path

from fpdf import FPDF

from . import db, rules
from .paths import data_folder

# column widths in millimetres, on landscape A4 (277 mm usable)
COLUMNS = [
    ("Cod.", 13), ("Area", 30), ("Formazione / Addestramento", 52),
    ("Appl.", 11), ("Modalita", 24), ("Tutor referente", 32),
    ("Dal", 15), ("Al", 15), ("Sess.", 11), ("Svolte", 12), ("Ore", 11),
    ("Stato", 22), ("Entro il", 15), ("Verifica", 14),
]

HEADER_GREY = (238, 241, 245)
STATE_FILLS = {
    "Completata": (198, 239, 206),
    "In corso": (189, 215, 238),
    "Da pianificare": (252, 228, 214),
    "N.A.": (217, 217, 217),
}


class Form(FPDF):
    def __init__(self, header: dict, form_code: str):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.details = header
        self.form_code = form_code
        self.set_auto_page_break(auto=True, margin=12)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 8)
        self.cell(45, 5, self.form_code, border=1, align="L")
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


def _details_row(pdf: FPDF, entries: list[tuple[str, str, int]]) -> None:
    for label, value, width in entries:
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(28, 6, label, border=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(width, 6, value or "", border=1)
    pdf.ln()


def generate(
    conn: sqlite3.Connection, plan_id: int, destination: Path | None = None
) -> Path:
    header = conn.execute(
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
        (plan_id,),
    ).fetchone()
    if header is None:
        raise ValueError(f"plan {plan_id} does not exist")

    modules = rules.module_summary(conn, plan_id)

    code = db.read_setting(
        conn, db.KEY_FORM_CODE, db.DEFAULT_FORM_CODE
    ) or db.DEFAULT_FORM_CODE
    pdf = Form(dict(header), code)
    pdf.add_page()

    reasons = ["Nuova funzione", "Cambio funzione", "Addestramento", "Formazione"]
    chosen = (header["motivo"] or "").lower()
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(28, 6, "Motivo", border=1)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(249, 6, "      ".join(
        f"{m} {'[X]' if m.lower() == chosen else '[  ]'}" for m in reasons
    ), border=1, new_x="LMARGIN", new_y="NEXT")

    _details_row(pdf, [
        ("Nome e Cognome", header["risorsa"], 77),
        ("Reparto", header["reparto"], 60),
        ("Mansione", header["mansione"], 56),
    ])
    _details_row(pdf, [
        ("Responsabile", header["responsabile"], 77),
        ("Tutor", header["tutor"], 60),
        ("Data inizio", _full_date(header["data_inizio"]), 56),
    ])
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(*HEADER_GREY)
    for title, width in COLUMNS:
        pdf.cell(width, 7, title, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for m in modules:
        fill_colour = STATE_FILLS.get(m["stato"])
        values = [
            m["codice"], m["area"][:24], m["titolo"][:44], m["applicabile"],
            (m["modalita"] or "")[:18], (m["tutor_referente"] or "")[:26],
            _short_date(m["dal"]), _short_date(m["al"]),
            str(m["sessioni_pianificate"]), str(m["sessioni_svolte"]),
            f"{m['ore_svolte']:g}", m["stato"],
            _short_date(m["entro_il"]), m["esito"] or "",
        ]
        for (_, width), value in zip(COLUMNS, values):
            filled = fill_colour is not None and value == m["stato"]
            if filled:
                pdf.set_fill_color(*fill_colour)
            pdf.cell(width, 4.8, value, border=1, align="C", fill=filled)
        pdf.ln()

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*HEADER_GREY)
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
    for label in ("Data", "Firma Risorsa", "Firma Tutor", "Firma Responsabile"):
        pdf.cell(69, 8, f"{label}: ______________________", border=0)
    pdf.ln()

    if destination is None:
        folder = data_folder() / "dati" / "stampe"
        folder.mkdir(parents=True, exist_ok=True)
        name = header["risorsa"].replace(" ", "_")
        destination = folder / f"Piano_formazione_{name}_{date.today():%Y%m%d}.pdf"

    pdf.output(str(destination))
    return destination


def _short_date(iso: str | None) -> str:
    """'2026-09-07' -> '07/09'."""
    return f"{iso[8:10]}/{iso[5:7]}" if iso else ""


def _full_date(iso: str | None) -> str:
    """'2026-09-07' -> '07/09/2026'."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else ""
