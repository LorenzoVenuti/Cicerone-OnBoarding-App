"""Genera il foglio di istruzioni per chi usa il programma.

    .venv/bin/python crea_istruzioni.py

Produce `docs/istruzioni.pdf`. Si rigenera quando l'app cambia: il PDF viene
versionato, cosi' chi lo consegna non deve avere Python.

E' scritto per una persona che non ha mai visto il programma e non aprira' mai
un terminale. Quindi: niente gergo, ogni schermata descritta per come appare, e
per ogni cosa che puo' andare storta una riga che dice cosa fare.
"""

from pathlib import Path

from fpdf import FPDF

BLU = (31, 62, 122)
GRIGIO = (90, 98, 110)
GIALLO = (255, 248, 225)
BORDO_GIALLO = (236, 217, 160)

LOGO = Path("app/risorse/logo.jpeg")
DESTINAZIONE = Path("docs/istruzioni.pdf")


class Foglio(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIGIO)
        self.cell(0, 6, "Cicerone - istruzioni", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIGIO)
        self.cell(0, 6, f"pagina {self.page_no()}", align="C")

    # --- mattoncini ---

    def titolo(self, testo: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*BLU)
        self.multi_cell(0, 7, testo, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def paragrafo(self, testo: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 35, 45)
        self.multi_cell(0, 5.2, testo, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def passo(self, numero: int, testo: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BLU)
        self.cell(7, 5.2, f"{numero}.", new_x="RIGHT", new_y="TOP")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 35, 45)
        self.multi_cell(0, 5.2, testo, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def riquadro(self, titolo: str, testo: str) -> None:
        self.ln(1)
        alto = 5.0 * (1 + len(testo) // 95) + 9
        y = self.get_y()
        self.set_fill_color(*GIALLO)
        self.set_draw_color(*BORDO_GIALLO)
        self.rect(self.l_margin, y, self.w - self.l_margin - self.r_margin, alto, style="DF")
        self.set_xy(self.l_margin + 3, y + 2.5)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*BLU)
        self.cell(0, 4.5, titolo, new_x="LMARGIN", new_y="NEXT")
        self.set_x(self.l_margin + 3)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(60, 55, 30)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 6, 4.6, testo,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + alto + 3)


def costruisci() -> Path:
    pdf = Foglio()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    # copertina
    if LOGO.exists():
        pdf.image(str(LOGO), x=20, y=18, w=26)
    pdf.set_xy(52, 22)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*BLU)
    pdf.cell(0, 10, "Cicerone", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(52, 33)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 6, "Come installarlo e come si usa", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(52)

    pdf.paragrafo(
        "Cicerone tiene l'agenda della formazione dei nuovi assunti: quando si "
        "fissa, si sposta o si annulla un incontro, avvisa da solo il tutor e la "
        "persona in formazione, e manda a entrambi l'appuntamento da mettere in "
        "calendario. Il piano formativo per la certificazione si compila da se' "
        "con quello che c'e' in agenda, e si stampa gia' nel formato da firmare."
    )
    pdf.paragrafo(
        "Non serve installare nient'altro sul computer: nessun programma di "
        "supporto, nessuna configurazione tecnica."
    )

    pdf.titolo("1. Installare il programma")
    pdf.passo(1, "Copiare sul computer il file Cicerone-v1.0.zip che si trova "
                 "sulla chiavetta. Conviene metterlo sulla Scrivania.")
    pdf.passo(2, "Fare doppio clic sul file: comparira' accanto l'icona blu di "
                 "Cicerone.")
    pdf.passo(3, "Trascinare Cicerone nella cartella Applicazioni, insieme agli "
                 "altri programmi. Il file zip a quel punto si puo' cestinare.")
    pdf.passo(4, "Aprire Cicerone con un doppio clic. La prima volta puo' "
                 "metterci qualche secondo in piu'.")

    pdf.riquadro(
        "Se il Mac dice che il programma non puo' essere aperto",
        "Succede quando il file arriva da internet invece che da una chiavetta. "
        "Aprire le Impostazioni di Sistema, andare in Privacy & Security, "
        "scorrere fino in fondo: c'e' un messaggio su Cicerone con accanto il "
        "pulsante Open Anyway. Premerlo e confermare. Va fatto una volta sola."
    )

    pdf.titolo("2. Il primo avvio: da dove partono le email")
    pdf.paragrafo(
        "Alla prima apertura Cicerone chiede da quale programma di posta far "
        "partire gli avvisi. Compare una finestra con l'elenco dei programmi "
        "installati e, sotto ciascuno, gli indirizzi che ha gia' configurati."
    )
    pdf.passo(1, "Scegliere il programma con l'indirizzo di lavoro: di norma "
                 "Outlook. Se sotto un programma c'e' scritto in rosso che non "
                 "ha nessun indirizzo, quello non va scelto.")
    pdf.passo(2, "Scegliere l'indirizzo mittente, cioe' quello da cui i colleghi "
                 "vedranno arrivare gli avvisi.")
    pdf.passo(3, "Scrivere il proprio indirizzo nel campo della prova e premere "
                 "Invia prova. Aspettare l'esito: compare sotto, in verde se e' "
                 "partita, in rosso con il motivo se non ce l'ha fatta.")
    pdf.passo(4, "Se la prova e' arrivata nella propria posta, premere Salva.")

    pdf.riquadro(
        "Il Mac chiedera' il permesso di controllare il programma di posta",
        "E' normale e va concesso: e' cosi' che Cicerone riesce a scrivere le "
        "email al posto vostro. Se per sbaglio si nega, si rimedia dalle "
        "Impostazioni di Sistema, in Privacy & Security, alla voce Automation."
    )

    pdf.add_page()

    pdf.titolo("3. Gli avvisi non partono finche' non lo si decide")
    pdf.paragrafo(
        "Appena installato, Cicerone prepara gli avvisi e li mette in elenco, ma "
        "non li spedisce. E' voluto: permette di vedere cosa manderebbe prima di "
        "lasciargli scrivere ai colleghi. In cima alla finestra c'e' un riquadro "
        "giallo che lo ricorda."
    )
    pdf.paragrafo(
        "Quando si e' pronti: aprire la scheda Mail inviate e spostare su ON "
        "l'interruttore Invio automatico email. Da quel momento gli avvisi "
        "partono da soli. Si puo' rimettere su OFF quando si vuole."
    )
    pdf.paragrafo(
        "Gli avvisi preparati mentre era spento non vanno persi: restano in "
        "elenco e si spediscono tutti insieme con il pulsante Riprova tutte."
    )

    pdf.titolo("4. Le schede del programma")
    pdf.paragrafo(
        "Agenda - gli incontri giorno per giorno. I giorni gia' passati stanno "
        "raccolti in fondo e si aprono con un clic. La striscia colorata a "
        "sinistra dice l'area dell'argomento, non se l'incontro si e' tenuto."
    )
    pdf.paragrafo(
        "Settimana - gli stessi incontri sul calendario della settimana."
    )
    pdf.paragrafo(
        "Piano ISO - il piano formativo, che si compila da solo con quello che "
        "c'e' in agenda. Le caselle gialle di verifica si riempiono a mano. Il "
        "pulsante di stampa produce il documento gia' pronto da firmare."
    )
    pdf.paragrafo(
        "Moduli - l'elenco degli argomenti da cui nasce il piano di ogni nuovo "
        "assunto, con il colore di ciascuna area."
    )
    pdf.paragrafo(
        "Persone - la rubrica. Perche' qualcuno riceva gli avvisi deve avere qui "
        "il suo indirizzo email: se ne manca qualcuno, il programma lo segnala in "
        "cima."
    )
    pdf.paragrafo(
        "Mail inviate - tutto quello che e' stato spedito: quando, a chi, con che "
        "testo. Il pulsante Vedi rilegge il messaggio esatto che e' partito."
    )

    pdf.titolo("5. Se qualcosa non va")
    pdf.paragrafo(
        "Un avviso non e' partito - aprire Mail inviate: accanto alla riga c'e' "
        "il motivo. Le due cause piu' comuni sono che l'invio automatico e' "
        "spento, e che il programma di posta non e' riuscito a spedire perche' "
        "va rifatto l'accesso. Sistemato il motivo, il pulsante Riprova rimanda "
        "quello che era rimasto indietro."
    )
    pdf.paragrafo(
        "Un collega non riceve niente - controllare in Persone che abbia "
        "l'indirizzo email: senza, non c'e' dove mandarlo."
    )
    pdf.paragrafo(
        "Il programma non si apre - riprovare una seconda volta; se insiste, "
        "vedere il riquadro della pagina precedente sul messaggio del Mac."
    )

    pdf.titolo("6. Dove finiscono i dati")
    pdf.paragrafo(
        "Tutto quello che si inserisce resta su questo computer, dentro il "
        "programma: non viene mandato da nessuna parte e non e' su internet. "
        "Cicerone ne tiene da parte una copia al giorno, e una copia in piu' ogni "
        "volta che viene aggiornato."
    )
    pdf.riquadro(
        "Un aggiornamento non fa perdere niente",
        "Quando arrivera' una versione nuova bastera' sostituire il programma: "
        "gli incontri, le persone e lo storico restano dove sono, e vengono "
        "adattati da soli alla versione nuova."
    )

    DESTINAZIONE.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(DESTINAZIONE))
    return DESTINAZIONE


if __name__ == "__main__":
    percorso = costruisci()
    print(f"fatto: {percorso} ({percorso.stat().st_size // 1024} KB)")
