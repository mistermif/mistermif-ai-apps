# Mistermif AI 0.4 — specifica del copilota di bordo

Questa specifica descrive il comportamento previsto. Non implica che tutte le
funzioni siano già operative nella versione corrente.

## Obiettivo

Mistermif AI deve migliorare la vita a bordo attraverso osservazione continua,
memoria locale, analisi storica, consigli e notifiche. Le protezioni urgenti
restano automazioni locali deterministiche. L'assistente non modifica
autonomamente inverter, BMS, firmware o protezioni elettriche.

## Profilo del mezzo

L'onboarding conversazionale raccoglie progressivamente:

- costruttore, modello, anno e dimensioni della caravan;
- disposizione, lato tendalino, finestre e orientamento convenzionale del muso;
- frigorifero, clima, boiler, batteria e fotovoltaico;
- sensori installati e loro posizione fisica;
- preferenze dell'equipaggio e soglie di notifica;
- dispositivi che possono essere comandati autonomamente.

Ogni dato deve riportare provenienza, data di aggiornamento e livello di
affidabilità. L'utente può correggerlo in qualsiasi momento.

## Stati di mobilità

Il motore usa GPS, velocità e tempo per distinguere:

1. `fermo`: nessuno spostamento significativo;
2. `partenza_probabile`: movimento coerente per un intervallo minimo;
3. `in_viaggio`: percorso attivo e campionamento dinamico;
4. `arrivo_probabile`: posizione stabile dopo un viaggio;
5. `piazzato`: fermo nella stessa area per circa due ore e conferma dell'utente.

Soglie, raggio e tempi devono essere configurabili. Salti GPS, coordinate non
valide e spostamenti brevi non devono incrementare la distanza.

## Diario viaggi e contachilometri GPS

Durante un viaggio vengono registrati, con frequenza adattiva:

- posizione, distanza stimata, durata, soste e velocità media;
- temperatura, umidità e pressione atmosferica;
- condizioni meteo e allerte incontrate;
- produzione, carica, scarica e consumi energetici disponibili;
- temperature interne e tecniche;
- anomalie, notifiche e note dell'utente.

Il contachilometri è una stima GPS e non sostituisce quello legale del veicolo.
Il riepilogo contiene qualità del segnale e distanza scartata dai filtri.

I file esportabili vengono salvati esclusivamente sotto:

```text
mistermif_ai/viaggi/
├── archivio/
├── percorsi/
├── riepiloghi/
└── allegati/
```

Il database operativo rimane nel volume dati privato dell'app.

## Riconoscimento campeggio e piazzola

Dopo l'arrivo il sistema:

- confronta le coordinate con luoghi già memorizzati;
- consulta soltanto fonti esterne autorizzate;
- propone il campeggio più probabile mostrando fonte e distanza;
- chiede conferma, numero piazzola e ampere disponibili;
- chiede orientamento del muso e lato esposto al sole;
- registra accesso, servizi, scarichi, ombra, rumore e note personali.

Park4night potrà essere collegato soltanto tramite API, partnership o altro
accesso ufficialmente autorizzato. Sono vietati scraping, elusione del login e
copia massiva del database.

## Preparazione dei viaggi

Quando l'utente annuncia una destinazione, il copilota confronta:

- viaggi e soste precedenti;
- previsioni lungo il percorso e nel luogo di arrivo;
- vento, raffiche, temporali, gelo e caldo;
- caratteristiche e corrente della piazzola;
- problemi, consumi e temperature osservati in passato.

Produce una lista motivata di precauzioni senza inventare prezzi, disponibilità
o regolamenti non verificati.

## Meteo e ambiente

GPS, previsioni e sensori interni/esterni alimentano consigli e allerte per:

- tendalino e oggetti esterni in caso di vento;
- temporali, grandine, pioggia intensa, gelo e caldo;
- opportunità di arieggiare e rischio condensa;
- esposizione solare della piazzola;
- produzione fotovoltaica attesa;
- condizioni sfavorevoli per frigorifero e vani tecnici.

Ogni avviso deve indicare dato osservato, previsione, scadenza e azione suggerita.

## Frigorifero

Il modulo correla:

- temperatura frigorifero e future sonde interne;
- attivazione, durata e velocità delle ventole;
- temperatura del vano e temperatura esterna;
- umidità, pressione, esposizione solare e consumo energetico;
- tempo di raffreddamento e recupero dopo l'apertura.

Può suggerire ombreggiamento, controllo delle griglie, disposizione del carico o
manutenzione. Non deve attribuire una causa certa senza misure sufficienti.

## Energia e comfort

I riepiloghi giornalieri includono:

- produzione fotovoltaica e attendibilità dei contatori giornalieri;
- energia caricata e scaricata, corrente batteria e picchi;
- consumo medio, massimo, latente e per apparato disponibile;
- uso del climatizzatore;
- temperature interne, esterne e dei vani;
- sensori offline, bloccati o incoerenti;
- confronto con giornate simili e suggerimenti pratici.

## Notifiche e consigli

Le notifiche possono essere autonome sui canali Home Assistant configurati.
Devono essere deduplicate, avere priorità e rispettare una pausa minima. Il
copilota deve distinguere informazione, consiglio, avvertimento e allarme.

## Automazioni dinamiche

Un'automazione dinamica è creata, versionata e spiegata dall'assistente. Riceve
un obiettivo, un insieme di apparati autorizzati, vincoli rigidi e fattori di
contesto. Può decidere autonomamente quando agire senza chiedere conferma per
ogni esecuzione.

Esempio: l'obiettivo “proteggi la batteria e spegni il clima intorno al 30%” può
considerare SOC, tendenza, corrente, produzione fotovoltaica, ricarica esterna,
ora, previsione solare, stato di viaggio, temperatura e priorità del clima. Può
attendere mentre il SOC recupera, anticipare l'intervento quando le fonti stanno
per terminare o scegliere una soglia leggermente diversa entro il margine
approvato.

Ogni automazione deve dichiarare:

- obiettivo e apparati autorizzati;
- dati necessari e comportamento con dati mancanti;
- margine decisionale e vincoli rigidi non modificabili;
- tempo minimo fra azioni e isteresi;
- criteri di escalation e notifica;
- procedura di test, disattivazione e rollback;
- log di input, motivazione, comando ed esito verificato.

La creazione nella cartella dedicata è libera. L'attivazione che richiede un
nuovo collegamento esterno segue sempre la procedura di conferma.

## Modalità animali a bordo

La modalità viene attivata esplicitamente dall'utente e include almeno numero di
animali, intervallo previsto, contatto reperibile e strategia di emergenza.

Durante la modalità:

- il climatizzatore autorizzato è un carico prioritario;
- il risparmio energetico non può spegnerlo autonomamente;
- temperatura e funzionamento reale del clima sono controllati localmente;
- SOC, tendenza e produzione stimano il tempo residuo prima del rischio;
- le notifiche iniziano con largo anticipo e aumentano di priorità;
- perdita di sensori, clima o connettività è trattata come condizione incerta;
- una persona deve poter raggiungere la caravan o attivare un piano alternativo.

Il sistema non garantisce da solo la sicurezza di persone o animali. Allarmi
termici locali, sensori ridondanti e supervisione umana restano obbligatori.

## Autonomia e modifiche

Con l'interruttore generale attivo l'assistente può osservare, analizzare,
memorizzare, iniziare o chiudere un viaggio e inviare notifiche. Può lavorare
liberamente nella propria cartella.

Qualsiasi modifica esterna richiede sempre una conferma singola preceduta da:

- motivo;
- file o configurazioni coinvolti;
- rischio ed effetti attesi;
- backup e procedura di ripristino.

## Privacy e conservazione

Percorsi e coordinate sono dati sensibili. Restano locali salvo esportazione
esplicita. Devono essere disponibili cancellazione per singolo viaggio,
retention configurabile, esportazione e backup. Le richieste al modello remoto
devono ricevere soltanto il contesto necessario.

## Fasi di realizzazione

1. database strutturato e macchina a stati del viaggio;
2. mappatura configurabile delle entità Home Assistant;
3. raccolta, filtri GPS e riepiloghi;
4. campeggi, piazzole e onboarding;
5. meteo, frigorifero, energia e comfort;
6. notifiche, simulazioni e validazione con i sensori reali.
