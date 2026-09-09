"""Generates the user guide for whoever uses the program.

    .venv/bin/python make_guide.py

Produces `docs/istruzioni.pdf`. Regenerate it when the app changes: the PDF is
committed, so whoever hands it over does not need Python.

Its text is in Italian because the people using the program are, and it is
written for somebody who has never seen it and will never open a terminal: no
jargon, every screen described as it looks, and for everything that can go
wrong one line saying what to do.
"""

from pathlib import Path

from fpdf import FPDF

BLUE = (31, 62, 122)
GREY = (90, 98, 110)
YELLOW = (255, 248, 225)
YELLOW_BORDER = (236, 217, 160)

LOGO = Path("app/resources/logo.jpeg")
DESTINATION = Path("docs/istruzioni.pdf")


class Sheet(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, "Cicerone - istruzioni", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, f"pagina {self.page_no()}", align="C")

    # --- building blocks ---

    def heading(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*BLUE)
        self.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def paragraph(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 35, 45)
        self.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def step(self, number: int, text: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BLUE)
        self.cell(7, 5.2, f"{number}.", new_x="RIGHT", new_y="TOP")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 35, 45)
        self.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def box(self, title: str, text: str) -> None:
        self.ln(1)
        height = 5.0 * (1 + len(text) // 95) + 9
        y = self.get_y()
        self.set_fill_color(*YELLOW)
        self.set_draw_color(*YELLOW_BORDER)
        self.rect(self.l_margin, y, self.w - self.l_margin - self.r_margin, height, style="DF")
        self.set_xy(self.l_margin + 3, y + 2.5)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*BLUE)
        self.cell(0, 4.5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(self.l_margin + 3)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(60, 55, 30)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 6, 4.6, text,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + height + 3)


def build() -> Path:
    pdf = Sheet()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    # cover
    if LOGO.exists():
        pdf.image(str(LOGO), x=20, y=18, w=26)
    pdf.set_xy(52, 22)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 10, "Cicerone", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(52, 33)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, "Come installarlo e come si usa", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(52)

    pdf.paragraph(
        "Cicerone tiene l'agenda della formazione dei nuovi assunti: quando si "
        "fissa, si sposta o si annulla un incontro, avvisa da solo il tutor e la "
        "persona in formazione, e manda a entrambi l'appuntamento da mettere in "
        "calendario. Il piano formativo per la certificazione si compila da se' "
        "con quello che c'e' in agenda, e si stampa gia' nel formato da firmare."
    )
    pdf.paragraph(
        "Non serve installare nient'altro sul computer: nessun programma di "
        "supporto, nessuna configurazione tecnica."
    )

    pdf.heading("1. Installare il programma")
    pdf.step(1, "Copiare sul computer il file zip di Cicerone che si trova "
                 "sulla chiavetta. Conviene metterlo sulla Scrivania.")
    pdf.step(2, "Fare doppio clic sul file: comparira' accanto l'icona blu di "
                 "Cicerone.")
    pdf.step(3, "Trascinare Cicerone nella cartella Applicazioni, insieme agli "
                 "altri programmi. Il file zip a quel punto si puo' cestinare.")
    pdf.step(4, "Aprire Cicerone con un doppio clic. La prima volta puo' "
                 "metterci qualche secondo in piu'.")

    pdf.box(
        "Se il Mac dice che il programma non puo' essere aperto",
        "Succede quando il file arriva da internet invece che da una chiavetta. "
        "Aprire le Impostazioni di Sistema, andare in Privacy & Security, "
        "scorrere fino in fondo: c'e' un messaggio su Cicerone con accanto il "
        "pulsante Open Anyway. Premerlo e confermare. Va fatto una volta sola."
    )

    pdf.heading("2. Il primo avvio: da dove partono le email")
    pdf.paragraph(
        "Alla prima apertura Cicerone chiede da quale programma di posta far "
        "partire gli avvisi. Compare una finestra con l'elenco dei programmi "
        "installati e, sotto ciascuno, gli indirizzi che ha gia' configurati."
    )
    pdf.step(1, "Scegliere il programma con l'indirizzo di lavoro: di norma "
                 "Outlook. Se sotto un programma c'e' scritto in rosso che non "
                 "ha nessun indirizzo, quello non va scelto.")
    pdf.step(2, "Scegliere l'indirizzo mittente, cioe' quello da cui i colleghi "
                 "vedranno arrivare gli avvisi.")
    pdf.step(3, "Scrivere il proprio indirizzo nel campo della prova e premere "
                 "Invia prova. Aspettare l'esito: compare sotto, in verde se e' "
                 "partita, in rosso con il motivo se non ce l'ha fatta.")
    pdf.step(4, "Se la prova e' arrivata nella propria posta, premere Salva.")

    pdf.box(
        "Il Mac chiedera' il permesso di controllare il programma di posta",
        "E' normale e va concesso: e' cosi' che Cicerone riesce a scrivere le "
        "email al posto vostro. Se per sbaglio si nega, si rimedia dalle "
        "Impostazioni di Sistema, in Privacy & Security, alla voce Automation."
    )

    pdf.add_page()

    pdf.heading("3. Gli avvisi non partono finche' non lo si decide")
    pdf.paragraph(
        "Appena installato, Cicerone prepara gli avvisi e li mette in elenco, ma "
        "non li spedisce. E' voluto: permette di vedere cosa manderebbe prima di "
        "lasciargli scrivere ai colleghi. In cima alla finestra c'e' un riquadro "
        "giallo che lo ricorda."
    )
    pdf.paragraph(
        "Quando si e' pronti: aprire la scheda Mail inviate e spostare su ON "
        "l'interruttore Invio automatico email. Da quel momento gli avvisi "
        "partono da soli. Si puo' rimettere su OFF quando si vuole."
    )
    pdf.paragraph(
        "Gli avvisi preparati mentre era spento non vanno persi: restano in "
        "elenco e si spediscono tutti insieme con il pulsante Riprova tutte."
    )

    pdf.heading("4. Le schede del programma")
    pdf.paragraph(
        "Agenda - gli incontri giorno per giorno. I giorni gia' passati stanno "
        "raccolti in fondo e si aprono con un clic. La striscia colorata a "
        "sinistra dice l'area dell'argomento, non se l'incontro si e' tenuto."
    )
    pdf.paragraph(
        "Settimana - gli stessi incontri sul calendario della settimana."
    )
    pdf.paragraph(
        "Piano ISO - il piano formativo, che si compila da solo con quello che "
        "c'e' in agenda. Le caselle gialle di verifica si riempiono a mano. Il "
        "pulsante di stampa produce il documento gia' pronto da firmare."
    )
    pdf.paragraph(
        "Moduli - l'elenco degli argomenti da cui nasce il piano di ogni nuovo "
        "assunto, con il colore di ciascuna area."
    )
    pdf.paragraph(
        "Persone - la rubrica. Perche' qualcuno riceva gli avvisi deve avere qui "
        "il suo indirizzo email: se ne manca qualcuno, il programma lo segnala in "
        "cima."
    )
    pdf.paragraph(
        "Mail inviate - tutto quello che e' stato spedito: quando, a chi, con che "
        "testo. Il pulsante Vedi rilegge il messaggio esatto che e' partito."
    )

    pdf.heading("5. Se qualcosa non va")
    pdf.paragraph(
        "Un avviso non e' partito - aprire Mail inviate: accanto alla riga c'e' "
        "il motivo. Le due cause piu' comuni sono che l'invio automatico e' "
        "spento, e che il programma di posta non e' riuscito a spedire perche' "
        "va rifatto l'accesso. Sistemato il motivo, il pulsante Riprova rimanda "
        "quello che era rimasto indietro."
    )
    pdf.paragraph(
        "Un collega non riceve niente - controllare in Persone che abbia "
        "l'indirizzo email: senza, non c'e' dove mandarlo."
    )
    pdf.paragraph(
        "Il programma non si apre - riprovare una seconda volta; se insiste, "
        "vedere il riquadro della pagina precedente sul messaggio del Mac."
    )

    pdf.heading("6. Dove finiscono i dati")
    pdf.paragraph(
        "Tutto quello che si inserisce resta su questo computer, dentro il "
        "programma: non viene mandato da nessuna parte e non e' su internet. "
        "Cicerone ne tiene da parte una copia al giorno, e una copia in piu' ogni "
        "volta che viene aggiornato."
    )
    pdf.box(
        "Un aggiornamento non fa perdere niente",
        "Quando arrivera' una versione nuova bastera' sostituire il programma: "
        "gli incontri, le persone e lo storico restano dove sono, e vengono "
        "adattati da soli alla versione nuova."
    )

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(DESTINATION))
    return DESTINATION


if __name__ == "__main__":
    path = build()
    print(f"done: {path} ({path.stat().st_size // 1024} KB)")
