# Ottimizzazione adattiva del frigorifero

Stato: controllo base operativo dalla versione 1.1.0; riconoscimento avanzato di
porta, sole e ricerca tecnica automatica restano requisiti evolutivi.

## Obiettivo

Mistermif AI controlla esclusivamente le ventole autorizzate del vano
frigorifero per ottenere:

- temperatura interna bassa e soprattutto stabile;
- migliore scambio termico possibile nelle condizioni ambientali presenti;
- minore stress per frigorifero e ventole;
- consumi, rumore e accensioni inutili ridotti;
- consigli pratici quando il controllo delle ventole non può risolvere la causa.

Il controllo non modifica protezioni, alimentazione, gas o parametri interni del
frigorifero. Se esiste un controller locale può modificare soltanto i parametri
esterni autorizzati della sua strategia ventole: soglia iniziale, soglia al
100%, PWM iniziale e isteresi.

## Integrazione conversazionale senza pulsanti dedicati

Il controllo del frigorifero deve essere una capacità integrata di Mistermif AI,
non un pannello separato. Non deve comparire un interruttore dedicato nella
schermata principale.

L'assistente deve eseguire periodicamente una scoperta locale delle capacità.
Appena trova una ventola, un comando o sensori i cui nomi e unità potrebbero
ricondurre al frigorifero, deve avviare subito la procedura guidata. Non deve
attendere 48 ore per fare la prima richiesta.

La rilevazione iniziale deve cercare:

- un frigorifero o sensori con nomi e unità coerenti;
- i sensori minimi necessari;
- almeno un comando ventole realmente controllabile;
- dati aggiornati e privi di lunghi periodi `unknown` o `unavailable`;
- indizi sufficienti per proporre che gli apparati appartengano al frigorifero.

Alla prima rilevazione deve inviare una notifica Home Assistant con collegamento
alla chat di Mistermif AI e, se configurato, un messaggio Telegram informativo.
La notifica deve permettere all'utente di aprire la conversazione e fornire i
dati richiesti. La chat deve iniziare con una richiesta simile:

> Ho trovato una ventola e alcuni sensori che potrebbero appartenere al
> frigorifero. Mi indichi marca, modello e a quale parte corrisponde ogni sensore?
> Dopo la verifica vuoi autorizzarmi a monitorare il frigorifero e gestire
> esclusivamente queste ventole?

La richiesta deve elencare le entità trovate e chiedere conferma della loro
funzione. La stessa installazione non deve produrre notifiche ripetute: una firma
locale delle entità ricorda che la richiesta è già stata inviata. Una nuova
richiesta è ammessa se cambiano le entità, l'utente la richiede oppure la
precedente configurazione viene cancellata.

Una risposta negativa lascia il modulo inattivo. Dopo aver ricevuto i dati e
l'autorizzazione positiva, il monitoraggio e la creazione della regola iniziano
immediatamente. L'autorizzazione è persistente ma circoscritta alla ventola
diretta o ai parametri del controller elencati e può essere revocata in chat.
L'interruttore generale del potere decisionale
rimane il blocco immediato di tutte le azioni autonome.

## Identificazione del frigorifero e ricerca tecnica

Durante l'intervista iniziale, oppure quando vengono rilevate entità compatibili,
Mistermif AI deve chiedere:

- marca e modello esatto del frigorifero;
- tecnologia, se nota: assorbimento o compressore;
- fonte energetica normalmente utilizzata;
- posizione e tipo delle griglie di ventilazione;
- modello e caratteristiche delle ventole installate;
- eventuali modifiche già realizzate nel vano.

Prima di proporre una strategia deve cercare documentazione tecnica del modello,
privilegiando manuale del costruttore, istruzioni di installazione, bollettini
tecnici e ricambi ufficiali. Deve ricavare, quando realmente documentati:

- temperature e condizioni ambientali ammesse;
- classe climatica e prestazioni dichiarate;
- requisiti di ventilazione e distanze delle griglie;
- posizione consigliata di sonde e ventole;
- limiti che non devono essere superati;
- eventuali indicazioni del produttore per massimizzare lo scambio termico.

Ogni informazione deve conservare fonte e data di verifica. Recensioni, forum e
esperienze di altri utenti possono generare ipotesi da provare, ma non devono
essere presentati come parametri ufficiali. Se il modello non è identificato con
certezza, l'assistente deve chiedere foto della targhetta o ulteriori dati e non
deve assumere valori universali.

## Sensori e dispositivi

### Requisiti minimi per prendere il controllo

La gestione reale delle ventole è possibile soltanto con tutti questi elementi:

- sonda di temperatura installata sul radiatore superiore;
- sonda di temperatura esterna;
- ventola PWM comandabile e modulabile da Home Assistant, direttamente oppure
  attraverso un controller locale che espone i parametri della curva;
- sonda interna al frigorifero, cablata oppure senza fili.

Una sonda interna wireless è valida se fornisce aggiornamenti regolari, espone
lo stato di disponibilità e, quando previsto, il livello della batteria. Un dato
fermo, scaduto, `unknown` o `unavailable` sospende l'affinamento e impedisce che
la sola sonda venga usata per nuove decisioni.

La sonda sul radiatore superiore è il riferimento obbligatorio della regola
iniziale a 40 °C. Una sonda generica del vano non può sostituirla senza conferma
esplicita della sua posizione fisica.

Il modulo deve scoprire e validare, quando presenti:

- temperatura interna del frigorifero;
- temperatura dell'evaporatore;
- temperatura del condensatore o del vano tecnico;
- temperatura e umidità esterna;
- stato e velocità delle ventole;
- stato del frigorifero e della sua fonte energetica;
- eventuale sensore porta;
- posizione, orientamento, ora e produzione/irraggiamento solare disponibili.

Se i sensori minimi non sono disponibili o restituiscono `unknown` oppure
`unavailable`, il modulo non deve intervenire, non deve inventare valori e non
deve generare falsi guasti. Deve limitarsi a indicare quali misure mancano.

## Avvio immediato e prima fase di apprendimento

Dopo identificazione delle entità e autorizzazione, il sistema deve attivare una
regola iniziale prudente e contemporaneamente iniziare a raccogliere dati.

La regola predefinita è:

- ventole al **100% quando il sensore caldo confermato raggiunge 40 °C**;
- la soglia deve riferirsi esplicitamente al sensore dell'evaporatore,
  condensatore o vano tecnico identificato dall'utente;
- se non è chiaro quale sensore rappresenti il lato caldo, nessun comando viene
  eseguito finché l'utente non lo conferma;
- sotto la soglia di boost rimane valida la strategia precedente o manuale,
  evitando accensioni e spegnimenti rapidi;
- 40 °C resta il limite iniziale di boost e non può essere spostato verso valori
  più alti dall'apprendimento senza una nuova autorizzazione.

Per almeno 48 ore di funzionamento valido il sistema deve poi registrare
localmente:

- temperatura interna, evaporatore, vano tecnico ed esterna;
- umidità esterna;
- velocità e tempo di funzionamento delle ventole;
- velocità di raffreddamento e di recupero;
- oscillazione della temperatura interna;
- ora, posizione e orientamento della sosta;
- eventi compatibili con apertura porta o irraggiamento solare.

I campioni di soste diverse non devono essere mescolati senza conservare il
relativo contesto ambientale. Durante questo periodo la regola a 40 °C rimane
attiva; l'assistente può preparare strategie migliori ma le applica soltanto
entro i limiti già autorizzati e dopo confronto con i risultati precedenti.

## Algoritmo adattivo

Dopo aver raccolto dati sufficienti, il sistema dovrà stimare l'intervallo di
temperatura dell'evaporatore nel quale il frigorifero ottiene il miglior
raffreddamento interno nelle condizioni osservate.

La funzione obiettivo deve favorire, nell'ordine:

1. rispetto delle temperature di conservazione configurate dall'utente;
2. stabilità della temperatura interna;
3. capacità di recupero dopo una perturbazione;
4. riduzione delle temperature eccessive nel vano tecnico;
5. minore tempo e velocità delle ventole quando non portano benefici misurabili.

L'apprendimento può modificare soltanto una strategia ventole racchiusa entro
limiti rigidi configurati. Ogni nuova strategia deve attraversare simulazione,
modalità ombra e confronto con la strategia precedente. In caso di dati
incoerenti deve tornare alla strategia sicura predefinita.

## Riconoscimento degli eventi

### Apertura della porta

Con un sensore porta l'evento è esplicito. Senza sensore può essere soltanto
stimato attraverso un rapido aumento della temperatura interna, eventuale
aumento dell'umidità e successivo recupero. L'inferenza deve essere etichettata
come probabilistica e non usata da sola per segnalare un guasto.

### Sole sulla parete

Il sistema può stimare l'irraggiamento della parete confrontando:

- aumento ricorrente della temperatura del vano o condensatore;
- temperatura esterna e umidità;
- ora, orientamento e posizione della caravan;
- produzione fotovoltaica o altri indicatori solari disponibili;
- perdita di rendimento a parità di uso e strategia delle ventole.

Anche questa rimane un'inferenza finché non viene installato un sensore di
temperatura della parete o di irraggiamento.

## Consigli contestuali

Quando le ventole non riescono a compensare il problema, Mistermif AI deve
produrre indicazioni motivate, per esempio:

> Negli ultimi giorni tra le 12:00 e le 14:00 il vano tecnico si scalda mentre
> la temperatura interna smette di diminuire. Verifica se il sole colpisce la
> parete del frigorifero, se le griglie sono libere e se lo scarico dell'aria
> calda è efficace.

Il consiglio deve distinguere tra misura, andamento osservato e ipotesi. Non
deve presentare l'esposizione al sole o l'apertura della porta come certe senza
un sensore che le confermi.

## Sicurezza e controllo utente

- nessun pulsante dedicato: consenso richiesto e revocabile attraverso la chat;
- interruttore generale del potere decisionale sempre valido come arresto;
- modalità predefinita di osservazione dopo installazione o cambio sensori;
- limiti minimi e massimi delle ventole non apprendibili;
- registro locale di ogni decisione e del risultato osservato;
- ripristino immediato della strategia sicura precedente;
- nessun uso di AI cloud per il controllo rapido delle ventole;
- AI cloud facoltativa soltanto per analisi periodiche e consigli;
- nessuna azione se i dati richiesti sono assenti o non affidabili.

## Criteri prima dell'attivazione reale

- rilevazione automatica di entità compatibili e notifica immediata all'utente;
- marca e modello forniti oppure impossibilità dichiarata esplicitamente;
- sensore caldo e comando ventole confermati dall'utente;
- entità Home Assistant associate e unità di misura verificate;
- comportamento delle ventole provato manualmente;
- autorizzazione esplicita dell'utente alla sola gestione delle ventole;
- prova della regola iniziale: boost al 100% a 40 °C e ripristino della strategia
  precedente sotto soglia;
- avvio immediato del monitoraggio e della raccolta dati;
- almeno 48 ore di campioni per iniziare l'affinamento adattivo;
- simulazioni successive di sensori offline, porta aperta, caldo esterno e
  recupero prima di applicare strategie più evolute.
