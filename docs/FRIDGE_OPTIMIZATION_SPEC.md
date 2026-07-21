# Ottimizzazione adattiva del frigorifero

Stato: specifica per una prossima versione, non ancora operativa.

## Obiettivo

Mistermif AI dovrà controllare esclusivamente le ventole autorizzate del vano
frigorifero per ottenere:

- temperatura interna bassa e soprattutto stabile;
- migliore scambio termico possibile nelle condizioni ambientali presenti;
- minore stress per frigorifero e ventole;
- consumi, rumore e accensioni inutili ridotti;
- consigli pratici quando il controllo delle ventole non può risolvere la causa.

Il controllo non deve modificare protezioni, alimentazione, gas o parametri
interni del frigorifero.

## Integrazione conversazionale senza pulsanti dedicati

Il controllo del frigorifero deve essere una capacità integrata di Mistermif AI,
non un pannello separato. Non deve comparire un interruttore dedicato nella
schermata principale.

L'assistente deve eseguire periodicamente una scoperta locale delle capacità e
riconoscere da solo quando sono presenti:

- un frigorifero o sensori con nomi e unità coerenti;
- i sensori minimi necessari;
- almeno un comando ventole realmente controllabile;
- dati aggiornati e privi di lunghi periodi `unknown` o `unavailable`;
- un periodo di osservazione sufficiente;
- limiti e strategia di ripristino verificati.

Quando tutti i presupposti sono soddisfatti, deve presentarsi in chat con una
richiesta simile:

> Ho riconosciuto temperatura interna, evaporatore, ambiente e comando ventole.
> Ho raccolto 48 ore di dati validi e completato la modalità ombra. Vuoi
> autorizzarmi a gestire esclusivamente le ventole del frigorifero entro i limiti
> indicati?

La richiesta deve spiegare sensori trovati, dati mancanti, strategia proposta,
limiti, rischi e metodo di ripristino. Una risposta negativa lascia il modulo in
osservazione. L'autorizzazione positiva è persistente ma circoscritta alle sole
ventole e può essere revocata in chat. L'interruttore generale del potere
decisionale rimane il blocco immediato di tutte le azioni autonome.

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

## Sensori opzionali

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

## Prima fase: osservazione

Per almeno 48 ore di funzionamento valido il sistema deve lavorare in modalità
osservazione, senza cambiare la strategia delle ventole. Deve registrare
localmente:

- temperatura interna, evaporatore, vano tecnico ed esterna;
- umidità esterna;
- velocità e tempo di funzionamento delle ventole;
- velocità di raffreddamento e di recupero;
- oscillazione della temperatura interna;
- ora, posizione e orientamento della sosta;
- eventi compatibili con apertura porta o irraggiamento solare.

I campioni di soste diverse non devono essere mescolati senza conservare il
relativo contesto ambientale.

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

- marca e modello identificati o dichiarati esplicitamente non disponibili;
- documentazione e limiti tecnici registrati con le relative fonti;
- almeno 48 ore di campioni validi;
- entità Home Assistant associate e unità di misura verificate;
- comportamento delle ventole provato manualmente;
- simulazioni di sensori offline, porta aperta, caldo esterno e recupero;
- confronto in modalità ombra con la strategia attuale;
- richiesta autonoma dell'assistente quando tutti i criteri risultano veri;
- autorizzazione esplicita dell'utente alla sola gestione delle ventole.
