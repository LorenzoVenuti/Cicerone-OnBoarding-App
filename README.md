# Cicerone

Applicazione desktop per l'ufficio HR: gestisce la formazione di ogni nuovo
assunto, dall'agenda delle sessioni al piano formativo richiesto dalla
certificazione ISO, e avvisa da sola le persone coinvolte quando un
appuntamento viene creato, spostato o annullato.

Sostituisce un foglio di calcolo compilato a mano, e ne corregge il difetto
principale: nel foglio i totali e gli stati si scrivevano a mano e potevano
contraddire le righe sottostanti. Qui **il piano e' calcolato**, quindi non puo'
essere incoerente.

Il nome viene dal cicerone, la guida che accompagna qualcuno in un posto nuovo:
e' il mestiere del tutor.

## Per chi deve solo usarla

Non serve installare niente: ne' Python, ne' altro. Si riceve un pacchetto e ci
si fa doppio clic.

Le istruzioni passo passo, con cosa aspettarsi a ogni schermata, stanno in
**[docs/istruzioni.pdf](docs/istruzioni.pdf)**.

In breve:

1. Estrarre `Cicerone-v1.0.zip` con un doppio clic e spostare **Cicerone** dove
   si tengono i programmi.
2. Aprirlo con un doppio clic.
3. Al primo avvio l'app chiede **da quale programma di posta** far partire le
   notifiche, e permette di fare una prova prima di confermare.

L'invio automatico parte **spento**: le notifiche vengono preparate e
registrate, ma non spedite, finche' non lo si accende dalla scheda *Mail
inviate*. E' voluto, cosi' si puo' vedere cosa farebbe l'app prima di lasciarle
scrivere ai colleghi.

## Per chi ci lavora sopra

Serve Python 3.12 o superiore.

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python semina_esempio.py     # dati inventati, per sviluppare
    .venv/bin/python avvia.py              # finestra dell'app

Su Windows i comandi sono `.venv\Scripts\python`.

Solo il server, con ricaricamento automatico a ogni salvataggio:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8731

I test — 90, che coprono il calcolo del piano, la chiusura automatica, le
sovrapposizioni, l'invio e gli aggiornamenti dell'archivio:

    .venv/bin/python -m unittest discover -s app -p "test_*.py"

## Cosa fa

**Agenda** — le sessioni giorno per giorno. I giorni gia' passati stanno
raccolti in fondo, richiusi. Il colore a sinistra dice l'**area** del modulo
(Commerciale, IT, Ufficio Tecnico...), non lo stato.

**Settimana** — le stesse sessioni su un calendario, che si apre sempre sulla
settimana corrente.

**Piano ISO** — il piano formativo calcolato: una riga per modulo, con date,
conteggi, ore e stato ricavati dalle sole sessioni. Le colonne di verifica
restano compilabili a mano, perche' sono un giudizio di una persona. Si esporta
in PDF nel formato del modulo del sistema qualita', pronto da firmare.

**Moduli** — il catalogo da cui nasce il piano di ogni nuovo assunto, con il
colore di ciascuna area.

**Persone** — la rubrica. Una persona ha nome, cognome ed email, e puo' fare da
tutor su un piano ed essere la risorsa in formazione di un altro: non ci sono
due anagrafiche separate.

**Mail inviate** — il registro di ogni notifica: quando, a chi, con quale testo
e con che esito. Da qui si rilegge il testo spedito, si riprovano quelle non
partite e si accende o spegne l'invio automatico.

## Notifiche e inviti in calendario

Partono da sole in tre casi: sessione creata, spostata, annullata. Vanno ai
tutor della sessione **e** alla persona in formazione.

Ogni notifica porta un **invito per il calendario**, non solo il testo: chi la
riceve se lo ritrova come appuntamento da accettare. Ogni sessione ha un
identificativo suo, generato una volta sola: spostare o disdire tocca **quel**
preciso appuntamento. Due incontri fra le stesse persone — capita quando un
argomento e' lungo e si divide in piu' parti — non si possono confondere.
Uno spostamento **aggiorna** l'appuntamento esistente invece di disdirlo e
ricrearlo, cosi' nel calendario non sparisce per poi ricomparire.

L'app non ha credenziali di posta e non parla con nessun server: usa il
programma di posta gia' configurato sul computer, tramite Outlook su Windows e
Outlook o Mail su macOS. La mail risulta quindi spedita dalla persona, e non c'e'
nessuna casella di servizio da farsi creare.

Un dettaglio che conta: **"nessun errore" non vuol dire "spedita"**. Un
programma di posta puo' accettare un messaggio e lasciarlo nella posta in
uscita, o perderlo se non ha account configurati. Dopo l'invio l'app controlla
che il messaggio sia davvero uscito dalla coda, e se resta li' lo registra come
errore invece che come consegna.

## I dati

Stanno tutti in un file solo, `piano.db`, che vive **sul computer di chi usa il
programma** e non e' in questo repository, per scelta: contiene nomi, indirizzi
e piani formativi di persone reali.

- su macOS: `~/Library/Application Support/Cicerone/dati/`
- su Windows: accanto all'eseguibile

L'app ne fa **una copia al giorno** all'avvio, in `dati/copie/`, tenendo le
ultime dieci, e **una copia prima di ogni aggiornamento** che tocchi la
struttura dell'archivio. E' l'unica rete di sicurezza che esiste, perche' quel
file non e' su nessun server.

Per sviluppare si usa `semina_esempio.py`, che genera nomi inventati sul dominio
`@esempio.test`.

### Cosa c'e' nei dati di esempio, e cosa no

`semina_esempio.py` crea un archivio completo e realistico — una risorsa, 21
moduli, 28 sessioni su cinque settimane, alcune gia' svolte — perche' un
progetto che si clona e parte vuoto non si puo' provare, e i test hanno bisogno
di qualcosa su cui girare. Due delle persone generate sono **volutamente senza
indirizzo email**, per poter verificare che l'app segnali il problema invece di
fallire in silenzio.

Sono dati inventati, e il catalogo formativo e' **deliberatamente generico**:
descrive un inserimento come lo avrebbe una qualsiasi azienda manifatturiera. Il
catalogo vero di un'azienda e' un'informazione riservata — dice cosa produce, in
quali linee e come e' organizzata dentro — e per questo non sta nel codice.
Vive solo nell'archivio locale, e ci arriva in due modi: caricandolo da un foglio
di calcolo con `importa.py`, oppure scrivendolo dalla scheda **Moduli**.

Vale lo stesso per il **codice del modulo** stampato in testa al PDF: ogni
azienda ha il suo, preso dal proprio sistema qualita', e identifica l'azienda.
Nel codice c'e' solo un segnaposto (`MOD-FORM-01`); quello vero si imposta una
volta dal campo *Codice del modulo* nella scheda Piano ISO, e resta
nell'archivio.

In generale, la regola di questo progetto e': **nel repository stanno il
programma e i dati inventati; i dati veri e tutto cio' che identifica
un'organizzazione stanno nell'archivio locale, che non e' versionato.**

## Aggiornare senza perdere niente

Una versione nuova dell'app **adatta** l'archivio esistente, non lo ricrea. Ogni
archivio porta scritto dentro a che versione dello schema si trova, e all'avvio
vengono applicate solo le modifiche mancanti, dopo averne messo da parte una
copia.

Chi tocca lo schema aggiunge una migrazione: la procedura e le regole sono in
[CLAUDE.md](CLAUDE.md), i test in `app/test_aggiornamento.py`.

## Com'e' fatta

    app/db.py          schema, migrazioni e copie dell'archivio
    app/percorsi.py    dove stanno risorse e dati, in sviluppo e impacchettata
    app/regole.py      calcolo del piano, chiusura automatica, sovrapposizioni
    app/stampa.py      PDF del modulo ISO
    app/mail.py        composizione dei messaggi dai template
    app/calendario.py  inviti iCalendar
    app/invio.py       i programmi di posta, e la verifica che il messaggio parta
    app/importer.py    lettura una tantum del foglio di calcolo di partenza
    app/main.py        API e server
    app/web/           interfaccia: tre file, nessun framework, nessuna compilazione
    template_mail/     i testi delle mail, modificabili senza toccare il codice

Il server e' locale e la finestra e' nativa: l'app non e' un sito e non richiede
connessione. L'interfaccia non usa framework ne' CDN, e font e icone stanno
dentro il programma, perche' deve funzionare anche senza rete.

## Costruire il pacchetto

PyInstaller non compila per un sistema diverso dal proprio: il pacchetto macOS
si costruisce su macOS, quello Windows su Windows. Entrambi si possono produrre
dai workflow in `.github/workflows/`, avviandoli dalla scheda **Actions**.

In locale, su macOS:

    .venv/bin/pyinstaller --clean --noconfirm Cicerone.spec
    ditto --norsrc --noextattr --noqtn dist/Cicerone.app /tmp/C.app
    codesign -s - --force --deep /tmp/C.app
    rm -rf dist/Cicerone.app && ditto /tmp/C.app dist/Cicerone.app

I due passaggi con `ditto` e `codesign` non sono facoltativi: su un Mac con chip
Apple un pacchetto senza firma **non parte**, e gli attributi estesi che il
sistema attacca ai file fanno fallire la firma.

Per consegnarlo conviene comprimerlo, non copiare la cartella:

    ditto -c -k --keepParent dist/Cicerone.app Cicerone-v1.0.zip

Una chiavetta formattata per Windows (FAT32 o exFAT) non conserva i permessi di
esecuzione: copiandoci il pacchetto aperto, sull'altro computer non partirebbe.
Dentro uno zip i permessi viaggiano come dato e arrivano intatti.

L'icona si rigenera dal logo con `crea_icona.py` (richiede Pillow, che serve
solo a quello e non entra nel pacchetto).

## Licenza

MIT — vedi [LICENSE](LICENSE).

## Prima di metterci mano

[CLAUDE.md](CLAUDE.md) raccoglie le regole del dominio che dai sorgenti non si
deducono, e gli errori che costano di piu'. [ROADMAP.md](ROADMAP.md) dice cosa manca.
