# Automazioni dinamiche

## Principio

Mistermif AI ha pieno potere decisionale sulle automazioni che crea, ma solo
all'interno di un perimetro approvato. Il perimetro specifica apparati, servizi,
azioni consentite, limiti rigidi e condizioni di arresto.

“Creata dall'assistente” non significa “senza limiti”: un'automazione del clima
non ottiene automaticamente accesso a inverter, BMS, firmware o altri apparati.

## Decisione contestuale

Una soglia diventa un obiettivo con margine decisionale. L'assistente può usare:

- valore e tendenza del SOC;
- corrente batteria e carico;
- produzione fotovoltaica e previsione solare;
- ricarica da rete, generatore o altre fonti;
- orario e durata residua del giorno;
- stato fermo, campeggio o viaggio;
- temperature interne, esterne e tecniche;
- meteo e priorità dichiarate dall'utente.

Esempio: con obiettivo di spegnimento clima attorno al 30%, una ricarica reale in
crescita può giustificare l'attesa. Alle 18, in viaggio e senza fonti previste,
una discesa rapida può giustificare un intervento anticipato entro il margine
autorizzato.

## Ciclo di vita

1. l'utente descrive l'obiettivo;
2. l'assistente prepara automazione, vincoli e simulazioni nel workspace;
3. se serve un collegamento esterno, ne spiega motivo, rischio e rollback;
4. dopo l'approvazione viene attivata una versione identificabile;
5. ogni decisione registra input, motivazione, comando ed esito;
6. kill switch e disattivazione per singola automazione sono sempre disponibili;
7. una nuova versione viene prima simulata e può essere ripristinata.

### Stati tecnici

- **Bozza:** file creati solo nel workspace, non caricati e non eseguiti.
- **Simulazione:** input sintetici, zero chiamate ai servizi Home Assistant.
- **Ombra:** lettura dei sensori reali e registrazione della decisione, zero
  comandi.
- **Attiva:** esecuzione limitata alle azioni già autorizzate, con interruttore
  generale, cooldown, registro e rollback.

La promozione non può saltare simulazione e ombra. Un sensore non associato,
stale, `unknown` o `unavailable` blocca la decisione invece di essere convertito
in zero.

## Simulazioni conversazionali 0.6.0

L'utente descrive la condizione direttamente nella chat oppure chiede un
self-check completo. Il motore locale interpreta i valori e confronta da solo
il risultato con i vincoli di sicurezza per SOC basso, recupero solare,
sovraccarico della colonnina, presa esterna e animali a bordo. Ogni risultato
dichiara:

- dati di ingresso;
- limite elettrico virtuale;
- livello di avviso;
- decisione e motivazione;
- azioni consentite che avrebbe proposto;
- raccomandazioni ancora protette;
- esito della propria autoverifica;
- conferma che nessun servizio reale è stato chiamato.

I risultati sono salvati in
`/config/mistermif_ai/log/energy_safety_lab.jsonl`. La simulazione è
deterministica e non consuma richieste Gemini.

## Limiti critici

Richiedono sempre autorizzazione dedicata:

- nuovi apparati o nuove categorie di servizio;
- parametri dell'inverter;
- parametri BMS e soglie elettriche di protezione;
- firmware ESPHome;
- modifiche alla ventilazione tecnica;
- riavvio o spegnimento del sistema.

## Modalità animali a bordo

Questa modalità non è una normale ottimizzazione energetica. Il clima diventa
prioritario e non viene spento autonomamente per conservare batteria.

Il sistema deve:

- verificare con sensori indipendenti temperatura e funzionamento del clima;
- stimare autonomia e rischio prima di raggiungere una condizione critica;
- inviare notifiche progressive e ripetute sui canali configurati;
- segnalare immediatamente perdita di sensori, alimentazione o connettività;
- mantenere allarmi locali indipendenti dall'AI;
- richiedere un contatto reperibile e un piano di intervento umano.

Mistermif AI assiste, ma non costituisce da solo una garanzia di sicurezza per
persone o animali.
