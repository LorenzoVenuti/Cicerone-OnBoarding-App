# Piano Formazione — app di gestione onboarding

Sostituisce un foglio di calcolo compilato a mano con un'applicazione
desktop. Il foglio resta solo come sorgente dei dati iniziali: dopo la
migrazione non si tocca piu'.

## Origine

La richiesta di partenza aveva tre punti:

1. collegamento con la mail per gli inviti a calendario;
2. automatismo che a fine giornata segna la sessione verde (fatta) e OK (superata);
3. garanzia che cambiare il nome di un tutor non rompa il file.

Il punto 3 nell'Excel e' un problema reale: il nome del tutor e' una stringa usata
come chiave dalle formule. Nell'app i tutor sono un'anagrafica con id proprio, e
rinominare una persona non ha effetti collaterali.

## Decisioni prese

| Tema | Decisione |
|---|---|
| Ambito | Multi-risorsa: catalogo moduli riutilizzabile, un piano per assunto |
| Invito calendario | SI, invito .ics allegato alla mail (dal 2026-09-08; prima era esclusa). Ogni sessione ha un `UID` suo: spostare o disdire tocca **quell'** appuntamento, non un altro fra le stesse persone. Lo spostamento aggiorna l'invito esistente alzando `SEQUENCE`, non disdice e ricrea. Resta escluso Microsoft Graph, che richiederebbe credenziali e l'IT |
| Auto-completamento | Alla riapertura del programma. Segna `Svolta` + esito `OK` |
| Piattaforma | Windows, Outlook desktop installato |
| Invio | Automatico, via Outlook COM (nessuna credenziale). Fallback SMTP |

Nota ISO: segnare l'esito `OK` in automatico attribuisce un giudizio di efficacia
che nessuno ha espresso. La scelta e' stata confermata esplicitamente; le sessioni chiuse
in automatico restano marcate `chiusa_automaticamente` nel database, cosi' una
vista di revisione e' aggiungibile in seguito senza migrazioni.

## Modello dati

    persona            id, nome, cognome, email, reparto, attivo
                       -> tutor, responsabili e risorse sono tutte persone

    risorsa            id, persona_id, reparto, mansione, responsabile_id,
                       tutor_principale_id, data_inizio, motivo
                       motivo: nuova funzione | cambio funzione | addestramento | formazione

    modulo_catalogo    codice (M01..M21), area, titolo, modalita_default,
                       tutor_referente_default_id, ordine
                       -> il template da cui nasce ogni nuovo piano

    piano              id, risorsa_id, creato_il, chiuso_il
    piano_modulo       id, piano_id, codice, area, titolo, applicabile (SI/NO),
                       modalita, tutor_referente_id,
                       entro_il, verifica_chiusura, verifica_efficacia,
                       data_verifica, esito
                       -> le ultime cinque sono le colonne gialle ISO, a mano

    sessione           id, piano_id, piano_modulo_id (nullable), data,
                       ora_inizio, ora_fine, dettaglio, stato, esito_verifica,
                       note, chiusa_automaticamente, creata_il, modificata_il
                       stato: Pianificata | Confermata | Svolta | Rinviata | Annullata

    sessione_tutor     sessione_id, persona_id
                       -> n-a-n: nell'Excel i tutor di una sessione stavano
                          tutti in una cella sola, separati da virgola

    mail_log           id, sessione_id, tipo, destinatari, oggetto, corpo,
                       registrata_il, inviata_il, esito, errore, senza_email
                       tipo: nuova | spostamento | annullamento

    impostazione       chiave, valore
                       invio_email_automatico: 0 (default) | 1

## Regole di calcolo

Direzione unica: le sessioni sono i fatti, il piano e' derivato. Nessun valore
aggregato viene scritto a mano.

Per ogni modulo del piano:

    sessioni_valide  = sessioni del modulo con stato != Annullata, Rinviata
    sess_pianificate = conteggio di sessioni_valide
    sess_svolte      = conteggio sessioni con stato = Svolta
    ore_svolte       = somma (ora_fine - ora_inizio) delle sole Svolta
    dal / al         = data minima / massima di sessioni_valide

    stato modulo:
        applicabile = NO            -> N.A.
        sess_pianificate = 0        -> Da pianificare
        sess_svolte >= pianificate  -> Completata
        sess_svolte > 0             -> In corso
        altrimenti                  -> Pianificata

Colori (dalla formattazione condizionale dell'Excel, da conservare nella UI):

    Svolta / Completata   verde   #C6EFCE
    In corso              azzurro #BDD7EE
    Rinviata              arancio #FCE4D6
    Da pianificare        pesca   #FCE4D6
    Annullata             rosa    #F2DCDB
    N.A.                  grigio  #D9D9D9

## Auto-completamento

Gira all'avvio dell'app, non a un orario fisso: il PC alle 18:00 puo' essere spento.

Una sessione viene chiusa automaticamente se, tutte insieme:

- stato e' `Pianificata` o `Confermata`;
- e' passata: `data < oggi`, oppure `data = oggi` e sono almeno le 18:00;
- non e' stata riprogrammata (nessuna modifica di data/orario dopo la sua creazione)
  ne' sostituita da una sessione nuova sullo stesso modulo con data successiva.

Effetto: stato -> `Svolta`, esito_verifica -> `OK`, `chiusa_automaticamente` -> vero.
All'avvio l'app mostra il riepilogo di cosa ha chiuso, cosi' resta verificabile.

## Mail

Tre eventi generano una mail, sempre agli stessi destinatari: i tutor della
sessione e la risorsa in formazione.

- nuova sessione       -> giorno, orario, modulo, tutor
- spostamento          -> giorno e orario VECCHI e NUOVI, affiancati
- annullamento         -> giorno e orario annullati, motivo se presente

Il template testuale lo fornisce chi usa il programma. Fino ad allora si usa un segnaposto,
tenuto in un file separato e modificabile senza toccare il codice.

La consegna automatica e' controllata dal toggle **Invio automatico email**
nella schermata Mail. Il default e' OFF: in questo stato la composizione e la
registrazione proseguono, ma nessun sender viene chiamato e la voce resta nel
registro con esito `invio_disattivato`. Gli esiti principali sono `inviata`,
`invio_disattivato` ed `errore`.

Il registro conserva `registrata_il`, cioe' il momento di registrazione della
notifica. `inviata_il` viene valorizzato solo dopo una consegna riuscita.
Le voci bloccate o fallite possono essere riprovate. Il retry usa oggetto,
corpo e destinatari salvati nella voce originale e la aggiorna senza creare
duplicati. La cancellazione dal registro elimina soltanto `mail_log`.

Gli indirizzi della risorsa e di tutti i tutor associati vengono inclusi e
deduplicati in modo case-insensitive, mantenendo l'ordine.
Valori vuoti o composti soltanto da spazi sono considerati email mancanti; la
validazione sintattica completa degli indirizzi non fa parte di questo MVP.

Invio: `outlook.py` via COM su Windows. Su Mac, in sviluppo, l'invio scrive su
file invece di partire davvero, cosi' il resto e' testabile.

## Dati che il programma non puo' inventare

1. Indirizzi email dei tutor e della risorsa. Senza, l'automazione non ha
   destinatari. E' il blocco piu' urgente.
2. Il template delle tre mail.
3. Tre sessioni dell'agenda originale non hanno un modulo assegnato: vanno
   attribuite dall'app.
4. Cinque moduli non hanno nessuna sessione e risultano `Da pianificare`:
   sicurezza, policy, software gestionali, clienti estero e una delle linee
   di prodotto.
5. Il modulo del sistema qualita' va ancora stampato e firmato? Se si', l'app
   deve esportarlo in PDF con lo stesso impaginato.

## Dati di partenza

Il foglio di calcolo di origine contiene il piano di una persona reale e non fa parte
del repository. Struttura: una testata anagrafica, 21 moduli formativi M01-M21,
37 sessioni distribuite su cinque settimane, 21 tutor.

Per lavorare senza dati reali: `python semina_esempio.py` popola un archivio con
nomi inventati e la stessa struttura.
