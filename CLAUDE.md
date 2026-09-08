# Istruzioni per chi lavora su questo progetto

Leggi questo file prima di toccare il codice. Contiene le regole del dominio che
non si deducono dai sorgenti e gli errori che costano di piu'.

## Cos'e'

Applicazione desktop per la gestione della formazione aziendale. Gestisce la
formazione di ogni nuovo assunto: l'agenda delle sessioni, il piano formativo
richiesto dalla certificazione ISO, e le mail automatiche quando un appuntamento
viene creato, spostato o annullato.

Nasce da un foglio di calcolo compilato a mano. Quel foglio non e' piu'
la fonte: e' stato importato una volta e va considerato superato. Non scrivere
codice che legge o aggiorna file Excel, con la sola eccezione di
`app/importer.py`, che serve alla migrazione iniziale.

Chi usa il programma non e' una persona tecnica e non aprira' mai un terminale:
ogni cosa deve essere raggiungibile dall'interfaccia.

## Avvio

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python semina_esempio.py     # dati finti per lavorare
    .venv/bin/python avvia.py              # finestra dell'app

Solo backend, con ricaricamento automatico:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8731

Su Windows i comandi sono `.venv\Scripts\python`.

## Dove sta cosa

    app/db.py          schema SQLite e connessione
    app/percorsi.py    dove stanno risorse e dati, in sviluppo e nell'eseguibile
    app/regole.py      calcolo del piano, chiusura automatica, sovrapposizioni
    app/stampa.py      PDF del modulo ISO da firmare
    app/mail.py        composizione dei messaggi dai template
    app/invio.py       canali di invio: Outlook su Windows, file su Mac
    app/importer.py    lettura una tantum dell'Excel di partenza
    app/main.py        API HTTP e avvio del server
    app/web/           interfaccia: tre file, nessun framework, nessuna build
    template_mail/     i testi delle mail, modificabili senza toccare il codice
    semina_esempio.py  genera dati finti
    importa.py         importa i dati veri da un Excel

## Le quattro regole da non rompere

**1. Il piano e' calcolato, mai scritto.**
Le sessioni sono gli unici fatti. Date, conteggi, ore e stato di ogni modulo si
derivano da quelle, in `regole.riepilogo_moduli`. Non aggiungere colonne
aggregate nel database "per comodita' o per velocita'": duplicare un dato
calcolabile e' esattamente il difetto dell'Excel che questa app sostituisce.
Con qualche decina di sessioni per piano, ricalcolare costa nulla.

**2. La chiusura automatica gira all'avvio, non a un orario.**
Il requisito parla delle 18:00, ma un'app desktop a quell'ora puo' avere il
computer spento. `regole.chiudi_sessioni_passate` viene chiamata quando l'app
parte e recupera tutte le giornate arretrate. Deve restare idempotente: due
esecuzioni di fila non devono cambiare niente la seconda volta.
Chiude una sessione solo se e' ancora aperta, se e' passata, e se nessuno l'ha
riprogrammata. Segna `Svolta` piu' esito `OK`, e lascia `chiusa_automaticamente`
a 1: quel campo serve a distinguere un giudizio umano da uno automatico, non
toglierlo.

**3b. Tutor e dipendenti sono lo stesso tipo di profilo.**
Non esistono due anagrafiche separate: una persona ha nome, cognome ed email, e
puo' fare da tutor su un piano, essere la risorsa di un altro, o entrambe. Si
creano e si modificano dalla scheda Persone. L'email serve a ricevere le
notifiche: una modifica di piano parte verso i tutor della sessione **e** verso
il dipendente in formazione, non solo verso il coach.

**Le notifiche portano un invito per il calendario.** Dal 2026-09-08 non sono
piu' solo testo: allegano un `.ics` che scrive l'appuntamento nel calendario di
tutor e risorsa. Ogni sessione ha un `uid_calendario` generato una volta e mai
piu' cambiato, piu' una `revisione_calendario` che sale a ogni avviso. Servono a
una cosa sola, ma decisiva: **spostare o disdire tocca quell'appuntamento e
basta**. Due incontri fra le stesse persone — capita quando un argomento e'
lungo e si divide — hanno UID diversi, quindi disdire il primo non cancella il
secondo. Uno spostamento **aggiorna** l'invito esistente (stesso UID, revisione
piu' alta): non si disdice per poi ricreare, o l'impegno sparirebbe e
ricomparirebbe nel calendario di chi lo riceve. `METHOD:CANCEL` solo per
l'annullamento. Senza alzare la revisione i calendari scartano l'aggiornamento
credendolo un doppione.

**Il programma di posta non si indovina: si configura.** Su un computer possono
esserci Outlook e Mail, uno con l'account di lavoro e l'altro vuoto, e da fuori
non si distinguono: il profilo di Outlook puo' pesare centinaia di MB senza
avere un solo account attivo. Al primo avvio l'app interroga i programmi
presenti (`invio.diagnosi_canali`), mostra quali indirizzi hanno, fa scegliere
e salva la scelta in `impostazione` (`canale_mail`, `mittente_mail`). Finche'
non e' configurato, `stato.mail_configurata` e' falso e l'interfaccia lo chiede.

**"Nessun errore" non vuol dire "spedita".** AppleScript restituisce successo
anche quando il messaggio viene solo accodato, o quando il client lo accetta e
lo perde perche' non ha account: e' successo davvero, provandolo. Registrare
quella come una consegna e' il difetto peggiore possibile qui, perche' il
registro direbbe "inviata" e nessuno saprebbe mai il contrario. Per questo dopo
`send` gli script controllano che il messaggio **esca dalla coda**, e se resta
li' e' un errore. Non togliere quel controllo per rendere l'invio piu' veloce.

La consegna automatica e' una policy centrale, persistita in `impostazione`:
il default e' OFF. Anche con invio disattivato la notifica viene composta e
registrata in `mail_log` come `invio_disattivato`; il sender non viene chiamato.
Ogni voce conserva `registrata_il`; `inviata_il` viene valorizzato solo dopo
una consegna riuscita.
Dal registro si possono riprovare le voci bloccate o fallite e cancellare
soltanto la voce del registro. Il retry aggiorna la voce originale.

**3. Le persone si riferiscono per identita', mai per nome.**
Nell'Excel il tutor era una stringa usata come chiave, e rinominare qualcuno
rompeva il foglio: e' stato un problema reale segnalato dall'utente. Ogni
riferimento a una persona passa da `persona.id`. Una sessione puo' avere piu'
tutor: la relazione e' `sessione_tutor`, non un campo di testo.

**4. Le sessioni non si cancellano.**
Si annullano, restando nel piano con stato `Annullata`. Il piano formativo e' un
documento di certificazione: deve mostrare anche cosa e' stato disdetto.

**5. Le sovrapposizioni si segnalano, non si impediscono.**
`regole.sovrapposizioni` trova gli accavallamenti della risorsa e dei tutor;
l'interfaccia li mostra mentre si compila, e lascia salvare. A volte due
impegni sovrapposti sono voluti, e un programma che lo vieta viene aggirato.

**6. Il colore identifica l'area, non lo stato.**
In agenda (bordo sinistro) e sul calendario (sfondo del blocco) il colore dice
di che area formativa e' il modulo — Commerciale, IT, Ufficio Tecnico... — non
lo stato della sessione. Il colore vive sulla tabella `area` (una riga per
area), assegnato di default da `regole.assicura_colori_aree`, che gira all'avvio
ed e' idempotente: cosi' anche un archivio vecchio si popola da solo, senza
migrazioni a mano. Si cambia dalla scheda Moduli, e vale per tutti i moduli di
quell'area. Lo stato resta nelle pastiglie testuali; sul calendario l'annullata
si riconosce perche' barrata e attenuata. Il calendario si apre sempre sulla
settimana di oggi, non sulla prima sessione del piano.

## Dati e riservatezza

Il repository e' privato e **non contiene dati veri**, per scelta. Nel database
finiscono nomi, indirizzi e piani formativi di dipendenti reali.

- `dati/`, i file `.db` e i file `.xlsx` sono in `.gitignore`. Lasciali fuori.
- Non scrivere nomi, indirizzi email o nomi di prodotti aziendali reali nel
  codice, nei commenti, nei test o nei messaggi di commit.
- Per provare qualcosa usa `semina_esempio.py`: nomi inventati, dominio
  `@esempio.test`, e due persone deliberatamente senza email per verificare
  l'avviso.
- Se ti serve una funzionalita' che richiede dati veri, chiedi: non copiarli nel
  repository "solo per un test".

## Convenzioni

- Codice, nomi di funzioni e variabili, commenti e messaggi dell'interfaccia in
  italiano. Non e' consueto, ma il progetto e' coerente: mantienilo.
- I messaggi di commit invece sono in inglese, all'imperativo presente
  (`Add PDF export`, `Fix session overlap check`).
- Nessuna emoji, da nessuna parte.
- L'interfaccia non usa framework e non ha una fase di build: tre file in
  `app/web/`. Non introdurre React, bundler o dipendenze da CDN senza motivo
  forte: l'app deve funzionare offline sul computer dell'utente.
- Per la stessa ragione font e icone sono dentro il programma: Inter sta in
  `app/web/font/` (font variabile, un file solo, SIL Open Font License) e le
  icone sono forme SVG scritte a mano in `app/web/app.js`. Niente Google Fonts
  a runtime, niente librerie di icone.
- I riferimenti a CSS e JavaScript in `index.html` portano un `?v=N`. Alzalo
  quando cambi la struttura della pagina: il server manda gia' `no-store`, ma
  una cache vecchia sopravvissuta a un aggiornamento e' una giornata persa a
  cercare un bug che non esiste.
- Gli endpoint di `app/main.py` sono `async def` di proposito: FastAPI li esegue
  cosi' sull'unico thread dell'event loop, e la connessione SQLite condivisa
  resta sicura. Se ne aggiungi uno sincrono, il primo accesso al database
  fallira' con "SQLite objects created in a thread can only be used in that same
  thread".

## Come verificare una modifica

Non esiste ancora una suite di test: e' il primo debito da colmare, e se tocchi
`regole.py` conviene aggiungerne. Nel frattempo, i controlli minimi:

    # il piano si calcola e l'app risponde
    .venv/bin/python -c "from app import db, regole; print(regole.riepilogo_moduli(db.connetti(), 1))"
    .venv/bin/python -m uvicorn app.main:app --port 8731 &
    curl -s localhost:8731/api/stato

Se cambi la chiusura automatica, provala a orari diversi passando `adesso`:

    from datetime import datetime
    regole.sessioni_da_chiudere(conn, datetime(2026, 9, 5, 9, 0))

Se cambi il calcolo del piano, confronta i risultati con quelli precedenti sugli
stessi dati: i numeri erano stati verificati uno a uno contro l'Excel originale.

## Lavorare da due computer

Il progetto viene modificato da due macchine diverse, a volte lo stesso giorno.

- `git pull` prima di cominciare, sempre.
- Commit piccoli e frequenti, e push appena una modifica sta in piedi: lasciare
  lavoro non condiviso in locale e' il modo piu' facile per creare conflitti.
- Il database non e' versionato, quindi ogni computer ha i suoi dati: non
  aspettarti che lo stato dell'app sia lo stesso sulle due macchine.
- Se cambi lo schema in `app/db.py`, **aggiungi una migrazione**: modificare
  solo `SCHEMA` non basta, perche' `CREATE TABLE IF NOT EXISTS` non tocca le
  tabelle gia' presenti e la colonna nuova non comparirebbe sugli archivi
  esistenti. Si scrive `_migrazione_N(conn)` e la si aggiunge in fondo a
  `MIGRAZIONI`; il numero finisce in `PRAGMA user_version`, cosi' ogni archivio
  sa a che punto e'. Prima di applicarle l'app mette da parte una copia in
  `dati/copie/`. Le migrazioni gia' pubblicate non si modificano piu': sono
  girate su computer che non hai, e vanno scritte in modo da poter essere
  rieseguite senza danno. I test stanno in `app/test_aggiornamento.py`.

## Stato attuale e lavoro aperto

Funzionano: importazione dall'Excel, agenda, piano ISO calcolato con le colonne
di verifica compilabili, rubrica delle persone, chiusura automatica, mail alla
creazione, allo spostamento e all'annullamento, registro degli invii.

Funzionano inoltre: creazione di una risorsa e del suo piano dall'interfaccia,
catalogo dei moduli modificabile, calendario settimanale, avviso sulle
sovrapposizioni, esportazione PDF del modulo ISO, eseguibile Windows.

**L'applicazione gira su macOS e su Windows**, e le due piattaforme non sono
intercambiabili su due punti che non si deducono dal codice:

- l'invio via Outlook COM non esiste su macOS, quindi oggi su Mac
  `invio.scegli_canale()` ripiega su `InvioSuFile` e **le notifiche non
  partono**: vanno scritte in `dati/mail_non_inviate/`. Serve un canale vero,
  verosimilmente Outlook per Mac via AppleScript;
- l'eseguibile Windows non serve piu' come unico bersaglio: serve un `.app`, e
  con esso la questione di dove l'app scrive quando e' impacchettata.

L'elenco completo di cosa blocca la consegna e di cosa si potrebbe aggiungere
dopo sta in [ROADMAP.md](ROADMAP.md). Va tenuto aggiornato li', non qui: questo
file descrive le regole del dominio, non il lavoro da fare.
