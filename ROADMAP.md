# Cosa manca

Lo stato del progetto, in ordine di utilita'. Quello che gia' funziona sta nel
[README](README.md); qui c'e' il resto.

## Prima di installarlo su un computer nuovo

1. **Prova dell'invio sul computer di destinazione.** L'app pilota il programma
   di posta gia' configurato, e quale sia cambia da una macchina all'altra: la
   schermata di configurazione, al primo avvio, permette una prova reale prima
   di confermare. Finche' quella prova non e' riuscita li', l'invio non e'
   verificato.

2. **Gli indirizzi email in rubrica.** Senza, le notifiche non hanno
   destinatari: l'app lo segnala in cima e non fallisce in silenzio, ma il dato
   serve.

3. **I testi definitivi delle mail.** Quelli in `template_mail/` sono segnaposto
   funzionanti, modificabili senza toccare il codice.

4. **Decidere se l'invio automatico parte acceso.** Il default e' spento, ed e'
   la scelta giusta durante lo sviluppo; alla consegna va deciso.

## Firma del pacchetto

Il pacchetto viene firmato "ad-hoc": basta a farlo partire, ma non evita
l'avviso di macOS al primo avvio di un file scaricato da internet. Con un
account sviluppatore Apple si puo' firmare e notarizzare, e l'avviso sparisce.

Senza account c'e' un modo gratuito che funziona: consegnare il pacchetto su una
**chiavetta** o da una cartella di rete invece di scaricarlo. L'avviso scatta per
l'etichetta che macOS mette sui file presi da internet; passando da un supporto
locale quell'etichetta non c'e'.

Attenzione al formato del supporto: una chiavetta FAT32 o exFAT non conserva i
permessi di esecuzione, quindi il pacchetto va copiato **dentro uno zip**, dove i
permessi viaggiano come dato.

## Piu' avanti

1. **Canale SMTP di riserva**, se il programma di posta blocca l'automazione.
   L'interfaccia in `app/invio.py` e' gia' predisposta: serve una classe con
   `disponibile()` e `invia()`.
2. **Promemoria il giorno prima** della sessione.
3. **Esporta e importa l'archivio** dall'interfaccia, per travasi e ripristini
   senza passare dal terminale.
4. **Ricerca e filtri in agenda**, per persona, area o stato.
5. **Archiviare i piani conclusi**, cosi' l'elenco resta leggibile col tempo.
6. **Aggiornamento dell'app** senza sostituire a mano il pacchetto.
7. **Storico delle modifiche** di una sessione: in ottica di certificazione vale
   quanto il registro delle mail.
8. **Statistiche**: ore per area, tempi medi di completamento.

## Debito tecnico

- I test girano nel workflow macOS ma non in quello Windows. `pytest` non e' fra
  le dipendenze: la suite e' `unittest` e si esegue con
  `python -m unittest discover -s app -p "test_*.py"`.
- L'attesa che il messaggio esca dalla coda del programma di posta puo' durare
  fino a mezzo minuto. Non blocca piu' l'interfaccia, ma chi guarda la schermata
  di prova aspetta comunque.
- `app/importer.py` legge il foglio di calcolo di partenza: e' codice usa e
  getta per la migrazione iniziale, e non ha test.
