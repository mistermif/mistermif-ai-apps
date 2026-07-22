# mistermif AI

**mistermif AI** è un copilota intelligente per caravan basato su Home
Assistant. Unisce sensori, energia, GPS, meteo, memoria locale e conversazione
AI per spiegare cosa accade a bordo, inviare avvisi e coordinare esclusivamente
le azioni autorizzate.

Il progetto nasce su una caravan Knaus, ma l'architettura è pensata per essere
configurabile e adattabile ad altri camper e caravan.

> Il progetto è in sviluppo attivo. Questa pagina descrive soltanto capacità
> presenti nel codice della versione pubblicata. Le specifiche tecniche sono
> separate e non valgono come dichiarazione di una funzione disponibile.

## Punto della situazione

La versione **1.2.0** è una base già funzionante, installabile come app di Home
Assistant. Non può modificare liberamente la caravan:
lavora entro una whitelist precisa, mantiene le protezioni rapide in locale e
separa chiaramente funzioni operative, simulazioni e specifiche tecniche.

| Area | Stato attuale | Cosa fa realmente |
|---|---|---|
| Chat e memoria | Operativa | Dialoga e conserva localmente conversazioni, profilo del mezzo e informazioni autorizzate |
| Home Assistant | Operativa | Legge soltanto sensori ed entità ammessi dalla politica di sicurezza |
| Controllo apparati | Limitato | Può spegnere esclusivamente il climatizzatore configurato; Animali a bordo ne impedisce lo spegnimento |
| Simulazioni energetiche | Operative | Simula batteria, solare, colonnina, PZEM, presa esterna e clima senza comandare dispositivi reali |
| Generazione configurazioni | Operativa come bozza | Prepara plance, helper e automazioni dentro `/config/mistermif_ai`, con manifest e rollback |
| Meteo autonomo | Operativo | Analizza ogni 30 minuti sensori, Open-Meteo e Radar-DPC; Windy è opzionale |
| Revisione Gemini meteo | Operativa e selettiva | Nessuna chiamata se il quadro è sereno o stabile; massimo 10 valutazioni al giorno quando compare un rischio |
| Diario viaggi | Operativo | Riconosce partenza e arrivo, registra percorso e soste, produce report ed esportazioni CSV/GPX |
| Ventilazione frigorifero | Operativa con consenso | Ottimizza i parametri di un controller locale oppure gestisce direttamente un PWM semplice; garantisce il 100% a 40 °C |
| Apprendimento | Prima fase operativa | Registra osservazioni e risultati per posizione, senza modificare autonomamente codice o soglie |

### Cosa può fare autonomamente oggi

- eseguire il controllo meteo locale ogni 30 minuti;
- osservare barometro, temperatura e umidità esterna e confrontarne l'andamento;
- evitare notifiche duplicate e aumentare il livello solo se il rischio peggiora;
- chiedere una revisione Gemini soltanto quando i controlli locali la
  giustificano;
- riconoscere il movimento della caravan e compilare il diario del viaggio;
- inviare notifiche Home Assistant e, per urgenze configurate, Telegram;
- registrare localmente motivazioni, risultati e modifiche prodotte nel proprio
  workspace;
- applicare soltanto le azioni già presenti nella whitelist e bloccarle tutte
  tramite l'interruttore del potere decisionale.

### Limiti di sicurezza

- non modifica autonomamente parametri di inverter, BMS o ventilazione;
- non installa da solo una bozza nell'impianto reale senza il ciclo di prova e
  l'autorizzazione richiesta;
- non comanda TPMS o altri apparati non configurati e autorizzati;
- non ricava il nome di un campeggio dalle coordinate senza una fonte ufficiale;
- mantiene le simulazioni energetiche separate dai dispositivi reali;
- non sostituisce protezioni elettriche, allarmi gas/fumo, IT-Alert,
  Protezione Civile o verifiche professionali.

La direzione del progetto è trasformare queste funzioni in un unico copilota
capace di osservare, ricordare, simulare, consigliare e intervenire nel solo
perimetro autorizzato, mantenendo sempre un comando immediato per bloccarne
l'autonomia.

## Perché esiste

In una caravan i dati sono distribuiti tra inverter, batteria, sensori, clima,
frigorifero, meteo e dispositivi diversi. Mistermif AI aggiunge un livello
superiore capace di:

- osservare un contesto filtrato di Home Assistant;
- ricordare conversazioni, preferenze e informazioni utili;
- trasformare misure e previsioni in spiegazioni comprensibili;
- inviare consigli, avvertimenti e notifiche;
- eseguire soltanto azioni inserite esplicitamente nella politica di sicurezza;
- preparare file e correzioni in uno spazio separato dal sistema centrale.

Le protezioni elettriche e termiche urgenti restano automazioni locali,
deterministiche e indipendenti dall'AI e da Internet.

## Cosa funziona oggi — versione 1.2.0

- interfaccia web integrabile nella barra laterale di Home Assistant;
- provider AI selezionabile: locale, OpenAI, Groq oppure Gemini;
- ritentativi automatici e fallback gratuito da Gemini 3.5 Flash a
  Gemini 3.1 Flash-Lite in caso di errore temporaneo `503`;
- risposta adattiva: modello Lite e ragionamento minimo per le richieste brevi,
  Gemini 3.5 e ragionamento più profondo per analisi e decisioni;
- saluti e test rapidi isolati dai vecchi ricordi per evitare risposte fuori
  contesto;
- selezione locale dei soli sensori pertinenti prima dell'invio al modello;
- filtro ricorsivo degli attributi Home Assistant per rimuovere token,
  credenziali, SSID, IP e contatti anche dai dati annidati;
- sensori offline trattati come diagnosi incompleta, senza generare da soli
  falsi allarmi;
- Google Search opzionale con fonti per meteo, ristoranti, campeggi e ricambi;
- budget giornalieri separati per richieste cloud totali e automatiche;
- Groq Free supportato tramite Responses API compatibile;
- lettura filtrata delle entità Home Assistant autorizzate;
- memoria locale SQLite per conversazioni e note;
- campionamento locale continuo ogni cinque minuti;
- storico energetico separato per posizione e orientamento della sosta;
- confidenza locale che cresce solo con campioni GPS validi;
- workspace isolato sotto `/config/mistermif_ai`;
- backup controllato di `configuration.yaml` prima dell'inserimento dell'include;
- registro delle modifiche e inventario con hash SHA-256;
- interruttore persistente per bloccare il potere decisionale;
- interruttore persistente Animali a bordo che rende il clima prioritario;
- spegnimento del solo climatizzatore configurato;
- notifiche tramite un servizio Home Assistant `notify.*` configurato;
- blocco di BMS, firmware, ventilazione inverter e parametri critici;
- intervista locale al primo avvio per mezzo, motrice ed equipaggio;
- tre livelli operativi: emergenza, urgenza e allerta;
- collegamento compatibile con installazioni che usano già `/config/packages`.
- simulazioni energetiche richieste direttamente nella chat, completamente locali;
- generazione nel workspace di plancia, helper, automazione fissa e policy
  dinamica;
- interpretazione di SOC, corrente batteria, PZEM, presa esterna, solare,
  colonnina, clima, orario e animali descritti in linguaggio naturale;
- self-check completo dei sei scenari di sicurezza senza scaricare la batteria
  e senza comandare apparati;
- ciclo obbligatorio bozza → simulazione → ombra → attiva;
- backup automatico di ogni file generato prima di una sua sovrascrittura;
- registro locale di input, decisione e azioni che sarebbero state proposte.
- ponte privato di laboratorio/MCP, solo consultivo e autenticato con token
  locale, per stato filtrato, simulazioni e proposte;
- risultati delle simulazioni rappresentati con indicatori grafici di SOC,
  corrente, rete, solare, colonnina, severità e stato del self-check.
- sorveglianza meteo deterministica ogni 30 minuti senza token AI;
- fusione di sensori locali, Open-Meteo multimodello e Radar-DPC grandine;
- deduplicazione persistente ed escalation soltanto quando il quadro peggiora;
- monitoraggio locale di barometro, temperatura e umidità esterna, comprese le
  variazioni combinate nelle ultime ore;
- revisione Gemini dinamica solo in caso di nuovo rischio o peggioramento, con
  tetto indipendente e non superabile di 10 chiamate al giorno;
- diario GPS automatico con pianificazione in chat, soste, arrivo, report e
  esportazione CSV/GPX.
- scoperta locale di sensori e comandi riconducibili al frigorifero;
- notifica immediata e raccolta in chat di marca, modello e associazioni;
- autorizzazione persistente limitata alle entità confermate del frigorifero,
  senza accesso alla ventilazione inverter;
- riconoscimento automatico di un controller ESPHome con parametri giorno/notte
  oppure di una installazione semplice con PWM diretto;
- campionamento del frigorifero ogni minuto, controllo diretto 0–100% o taratura
  vincolata di temperatura iniziale, temperatura al 100%, PWM e isteresi;
- affinamento locale dopo una cronologia sufficiente, senza modificare firmware
  o superare i valori ammessi dal controller;
- blocco immediato del comando ventole tramite l'interruttore generale.
- modalità persistente **sola osservazione**, selezionabile in linguaggio
  naturale anche quando mancano sensori: nessun comando, ma lettura dei dati
  disponibili e suggerimenti prudenti;
- interpretazione semantica Gemini quando le regole locali non comprendono una
  risposta contestuale, con confidenza minima e richiesta di chiarimento;
- separazione rigida tra comprensione e autorizzazione: Gemini può spiegare
  l'intenzione ma non può concedere il controllo o eseguire comandi;

### Laboratorio esterno

Il gemello digitale resta sul Mac. Mistermif AI continua a vivere sul Raspberry,
dove conserva memoria, regole, contesto di Home Assistant e registro delle
decisioni. I due ambienti comunicano tramite un ponte privato autenticato:

```text
strumento sul Mac ── MCP locale ── token/LAN ── Mistermif AI sul Raspberry
     │                                      │
     └─ proposte e analisi                   ├─ stato HA filtrato
                                            ├─ memoria e vincoli
                                            └─ simulatore deterministico
```

Il ponte espone cinque strumenti consultivi: stato, confronto, simulazione,
self-check e proposta. Il risultato contiene un consenso esplicito (`agreed`,
`needs_revision` o `requires_user_authorization`) e viene registrato localmente.
Il ponte non espone strumenti di comando: non può spegnere apparati, cambiare
file, modificare BMS/inverter/firmware o aggirare l'interruttore del potere
decisionale. Un accordo consente quindi di preparare e collaudare una soluzione,
non di applicarla di nascosto.

La porta 8100 deve restare sulla rete locale: non aprirla sul router e non
pubblicarla su Internet. Il token non va mai salvato nella repo.

### Simulazioni conversazionali

La versione 0.6.0 elimina il pannello tecnico del laboratorio. La simulazione si
usa direttamente nella chat ed è indipendente dal provider AI: funziona anche
senza Gemini e quando i dispositivi ESP sono offline.

Esempi:

- `Simula batteria al 19%, senza sole, corrente -42 A e clima acceso`;
- `Simula colonnina 10 A, PZEM 720 W e presa esterna 1420 W`;
- `Simula batteria al 18%, cani a bordo e nessuna ricarica`;
- `Fai un test completo di tutte le simulazioni energetiche`.

Mistermif AI traduce la frase in uno snapshot virtuale, applica le regole locali,
controlla automaticamente isolamento, decisione, protezione della colonnina,
recupero energetico e tutela degli animali, quindi risponde con **coerente** o
**da correggere**. Specifica sempre i valori interpretati, le assunzioni, le
azioni che avrebbe proposto e conferma che le azioni reali eseguite sono zero.

Il backend può ancora preparare esclusivamente dentro `/config/mistermif_ai`:

- un package di helper e sensori virtuali;
- una plancia Lovelace YAML pronta da collegare;
- un'automazione fissa che genera soltanto un evento locale;
- una policy leggibile per le automazioni dinamiche;
- manifest, storico delle prove e copie di rollback.

Il self-check incluso copre sensori offline, batteria critica, recupero solare,
colonnina da 6 A, colonnina da 10 A con presa esterna e animali a bordo. Durante
una simulazione vengono eseguiti zero servizi Home Assistant: il consumo della
batteria reale causato dal test è sempre zero.

La modalità attiva rimane bloccata finché i sensori reali non saranno associati,
convalidati e osservati in modalità ombra. Questo evita che un nome errato o un
valore `unknown` producano un comando. In modalità ombra l'assistente registra
cosa avrebbe fatto senza cambiare alcuno stato.

L'associazione dei sensori per la modalità ombra resta disponibile tramite API e
configurazione assistita, ma non occupa più la schermata principale. Una prova
ombra resta inconcludente finché SOC, potenza rete/PZEM e produzione solare non
sono associati e validi.

### Console essenziale

La schermata principale mostra soltanto la chat e due interruttori:

- **Potere decisionale** abilita o blocca immediatamente tutte le azioni già
  comprese nella whitelist sicura dell'assistente;
- **Animali a bordo** applica un vincolo persistente alle analisi, alle
  simulazioni e ai comandi, impedendo lo spegnimento del clima finché resta
  attivo.

L'interruttore non autorizza modifiche a BMS, inverter, firmware o ventilazione.
Queste categorie rimangono protette e richiedono un intervento progettato e
convalidato separatamente.

Una piccola icona a ingranaggio apre le impostazioni tecniche: collegamento Home
Assistant, provider e modello AI, privacy, quote cloud, apprendimento locale,
profilo del mezzo, workspace, livelli di allarme e categorie protette. Queste
informazioni non occupano più la console principale.

Il backend espone inoltre un costruttore generale per bozze di tipo dashboard,
helper, automazione fissa, automazione dinamica, script e template. Le bozze
restano fuori da `packages/`, hanno un manifest locale e non vengono caricate da
Home Assistant finché non attraversano il ciclo di collaudo.

### Quale intelligenza artificiale scegliere

La sicurezza e le automazioni locali non dipendono da alcun provider. Cambiare
AI modifica la conversazione e la capacità di interpretazione, non i permessi
concessi all'assistente.

| Soluzione | Costo iniziale | Ricerca Internet in questa versione | Quando sceglierla |
|---|---:|---|---|
| `local` | gratuito | no | massima riservatezza, memoria e regole locali senza chat generativa |
| `gemini` Free | gratuito entro le quote del progetto | no con Gemini 3.5 Flash Free | ragionamento cloud senza carta di credito, usando dati HA e meteo già integrato |
| `groq` Free | gratuito entro le quote | no | risposte molto rapide e buona alternativa gratuita |
| `gemini` Paid | consumo a pagamento | Google Search Grounding con fonti | meteo contestuale, ristoranti, campeggi e ricambi aggiornati |
| `openai` | consumo a pagamento | no | qualità elevata; l'API è separata dall'abbonamento ChatGPT |

Quote, modelli e prezzi cambiano nel tempo: prima di attivare la fatturazione
verifica sempre le pagine ufficiali di [Gemini](https://ai.google.dev/gemini-api/docs/pricing),
[Groq](https://console.groq.com/docs/rate-limits) e
[OpenAI](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

#### Gemini gratuito

1. crea una chiave in Google AI Studio senza attivare la fatturazione;
2. seleziona `gemini` e inserisci la chiave in `ai_api_key`;
3. usa il modello stabile `gemini-3.5-flash`;
4. lascia `gemini_search_enabled` disattivato;
5. usa inizialmente 15 richieste giornaliere, di cui 5 automatiche.

Gemini 3.5 Flash offre input e output gratuiti entro i limiti del progetto, ma
Google Search Grounding non è disponibile nel Free Tier. I limiti reali sono
mostrati in Google AI Studio e prevalgono sempre sui tetti locali dell'app.
Se Google segnala un sovraccarico temporaneo, l'app ritenta la richiesta e,
senza Search attiva, passa automaticamente al modello gratuito
`gemini-3.1-flash-lite`. Le protezioni e le analisi locali non si interrompono.

Per ridurre la latenza, saluti e richieste molto brevi vengono gestiti da
Gemini 3.1 Flash-Lite con ragionamento `minimal` e senza inviare l'elenco dei
sensori, vecchie conversazioni o memorie. Le domande normali usano ragionamento
`low`; analisi energetiche,
meteo, sicurezza e decisioni automatiche restano su Gemini 3.5 Flash con
ragionamento `medium` e ricevono soltanto le entità pertinenti.

#### Gemini con fatturazione

Con un progetto a pagamento si può attivare `gemini_search_enabled`. Al momento
Google indica per i modelli Gemini 3 una franchigia di 5.000 prompt grounded al
mese, condivisa, seguita da tariffazione per query; input e output hanno costi
separati. Imposta limiti locali prudenti e controlla periodicamente la spesa.

Le modalità privacy sono:

- `local_only`: nessun invio al cloud;
- `redacted_cloud`: rimuove anche posizione, viaggi e profilo;
- `contextual_cloud`: consente posizione e contesto utile, ma rimuove sempre
  chiavi API, token, password, segreti, indirizzi IP e contatti.

I valori iniziali interni sono 15 richieste complessive al giorno e 5
automatiche. Il sotto-limite protegge una riserva per le richieste manuali. Se
Google Search è autorizzato, viene usato solo per richieste riconoscibili come
meteo, ristorante, campeggio o ricambio e le fonti vengono mostrate in fondo.

### Livelli di allarme

- **Emergenza:** intervento immediato e invio su Home Assistant più Telegram;
- **Urgenza:** intervento richiesto entro 10–15 minuti;
- **Allerta:** nessun intervento necessario, ma attenzione e monitoraggio.

I livelli descrivono priorità e tempi di risposta. Non sostituiscono protezioni
locali deterministiche per incendio, gas, temperatura, persone o animali.

### Intervista iniziale

Al primo avvio l'app chiede tipo, marca, modello e anno del mezzo. Per una
caravan richiede anche la motrice. Nomi e ruoli dell'equipaggio vengono
conservati esclusivamente nella memoria SQLite locale e sono esclusi dal
contesto cloud filtrato.

## Sorveglianza meteo autonoma 0.9

Il supervisore meteo lavora ogni 30 minuti senza usare un modello AI e quindi
senza consumare token. Combina sensori Home Assistant, GPS, previsione
multimodello Open-Meteo e, in Italia, il prodotto puntuale di probabilità di
grandine del Radar-DPC. Windy Point Forecast può essere aggiunto solo con una
chiave Professional: la chiave gratuita di test restituisce dati alterati e non
viene mai usata per decisioni di sicurezza.

Lo stato dell'ultimo evento è persistente. Un avviso non viene ripetuto finché
la severità e i fenomeni restano invariati. Una nuova notifica viene emessa
soltanto quando il quadro peggiora sensibilmente, compare grandine oppure viene
rilevato un temporale sviluppato. Le allerte ordinarie usano il servizio
`notify.*`; urgenze ed emergenze aggiungono Telegram quando sono configurati i
destinatari.

Le fonti esterne integrano, ma non sostituiscono, IT-Alert, Protezione Civile,
allarmi locali o decisioni dell'utente. Radar-DPC può avere copertura parziale o
dati non validati in tempo reale.

Fonti e condizioni d'uso: [Open-Meteo](https://open-meteo.com/en/docs),
[piattaforma Radar-DPC](https://mappe.protezionecivile.gov.it/it/mappe-e-dashboard-rischi/piattaforma-radar/)
e [Windy Point Forecast](https://api.windy.com/point-forecast/docs). Open-Meteo
richiede attribuzione CC BY 4.0; i dati Radar-DPC sono pubblicati con licenza
CC BY-SA 4.0. Windy resta completamente opzionale.

### Revisione Gemini su richiesta del rischio

Barometro, temperatura e umidità esterna vengono campionati localmente e
conservati per 24 ore. Il motore confronta la pressione e le variazioni
combinate di temperatura e umidità: un calo significativo genera prima una
valutazione deterministica. Gemini viene interrogato soltanto quando compare un
nuovo rischio o il quadro peggiora; con condizioni serene o stabili non parte
alcuna chiamata. Il budget `weather_ai_daily_limit` è separato dalla chat ed è
limitato dal programma a un massimo assoluto di 10 valutazioni al giorno.

Alla revisione vengono inviati soltanto il quadro meteo già sintetizzato e le
tre misure esterne; non vengono inviati coordinate precise, cronologia dei
viaggi, profilo dell'equipaggio, token o chiavi. Gemini può proporre al massimo
`allerta` o `urgenza`: non può dichiarare da solo un'emergenza e non sostituisce
le protezioni locali.

## Diario viaggi autonomo 0.9

Il GPS viene letto localmente ogni 30 secondi. Due campioni consecutivi sopra
5 km/h avviano un viaggio; una sosta prolungata, predefinita a due ore, chiude
il diario e viene interpretata come arrivo. Distanza, durata totale, tempo in
movimento e in sosta, velocità media e massima, numero di soste, temperatura,
umidità e pressione rimangono nel database SQLite locale.

È possibile scrivere in chat `Venerdì parto per il Camping Club degli Amici`:
la destinazione viene associata automaticamente alla partenza successiva.
`Fammi il report del viaggio` restituisce il riepilogo; `Esporta il viaggio`
prepara CSV e GPX. Coordinate e tracce non sono inviate al provider AI.

## Gestione operativa della ventilazione frigorifero

Mistermif AI cerca ogni minuto nomi ed entità riconducibili al frigorifero. Alla
prima scoperta invia una sola notifica e avvia la raccolta dati in chat. Non
esegue alcun comando finché marca, modello, quattro associazioni e consenso non
sono completi. L'utente conclude il flusso scrivendo, per esempio,
`Frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo`.

I requisiti minimi sono:

- **sonda sul radiatore superiore**, usata come riferimento caldo e come soglia
  iniziale per il boost;
- **sonda di temperatura esterna**, necessaria per distinguere il rendimento del
  frigorifero dalle condizioni ambientali;
- **ventola PWM controllabile da Home Assistant**, con comando e stato validi e
  possibilità di modulazione dallo 0% al 100%;
- **sonda di temperatura interna al frigorifero**, anche senza fili, purché sia
  integrata in Home Assistant e aggiornata con regolarità.

Servono inoltre marca e modello del frigorifero, associazione confermata delle
entità e autorizzazione dell'utente. Dopo il consenso parte immediatamente il
monitoraggio e la regola iniziale:
ventola al 100% quando la sonda del radiatore superiore raggiunge 40 °C. I dati
vengono registrati localmente per le successive analisi di rendimento.

Senza tutti e quattro i requisiti validi Mistermif AI potrà osservare e indicare
cosa manca, ma non prenderà il controllo della ventilazione.

Con un controller locale compatibile l'app modifica soltanto le entità
`select.*`, `number.*` o `input_number.*` che regolano avvio, piena velocità,
PWM iniziale e isteresi. Le correzioni avvengono al massimo ogni sei ore. Con
un'installazione priva di logica locale comanda direttamente la sola entità
`fan.*` o `number.*` autorizzata, usando una curva progressiva e isteresi.

L'autorizzazione è un confronto esatto e non può estendersi alle ventole
dell'inverter. Il pulsante generale del potere
decisionale blocca immediatamente anche questo comando. Stato e prova manuale
sono disponibili tramite `GET /api/fridge` e `POST /api/fridge/check`.

Scrivendo `limitati ad osservare e dammi solo suggerimenti` l'utente imposta
una scelta persistente che ha precedenza sulla procedura di configurazione. Le
entità mancanti vengono indicate come dati non disponibili, ma non impediscono
all'assistente di recepire l'istruzione e non provocano ulteriori richieste di
autorizzazione.

Non è necessario usare quella frase esatta. Le formulazioni chiare vengono
comprese localmente; risposte contestuali come `per adesso lascialo stare e
avvisami solo se noti qualcosa` vengono inviate a Gemini come richiesta compatta
di classificazione. Se la confidenza è inferiore al 70%, Mistermif AI domanda
che cosa si intende. Un risultato `authorize_control` non viene mai applicato:
per concedere comandi serve comunque la dichiarazione esplicita prevista dalla
politica di sicurezza.

La specifica dettagliata è disponibile in
[`docs/FRIDGE_OPTIMIZATION_SPEC.md`](docs/FRIDGE_OPTIMIZATION_SPEC.md).

## Architettura

```text
Sensori e automazioni Home Assistant
                 │
                 ▼
        filtro delle autorizzazioni
                 │
        ┌────────┼───────────────┐
        ▼        ▼               ▼
 automazioni rapide   mistermif AI
 e deterministiche    ├─ chat
                      ├─ memoria locale
                      ├─ analisi e consigli
                      ├─ azioni autorizzate
                      └─ ponte consultivo ← MCP sul Mac
```

Solo il contesto necessario viene inviato al provider AI selezionato. Database,
memoria e file operativi restano locali, salvo esportazione richiesta
dall'utente. In
modalità predefinita `local_only` non viene inviato alcun contenuto al modello
cloud; la modalità `redacted_cloud` è opzionale e applica filtri preventivi.

## Apprendimento locale

La versione corrente registra
campioni locali e li associa a un'identità anonima della sosta derivata da GPS e
orientamento. Campioni senza posizione non aumentano la confidenza e dati di
luoghi diversi non vengono mescolati.

L'apprendimento riguarda osservazioni e risultati: non modifica autonomamente
codice, firmware, soglie protette o parametri dell'impianto.

## Workspace isolato

I file creati dall'assistente vengono conservati in:

```text
/config/mistermif_ai/
├── packages/
├── plance/
├── automazioni/
├── script/
├── template/
├── helper/
├── laboratorio/
├── backup/
├── log/
└── manifest/
```

Prima di collegare il workspace viene salvata una copia di
`configuration.yaml`. Nel file centrale può essere aggiunto, dopo conferma,
soltanto il collegamento:

```yaml
homeassistant:
  packages: !include_dir_named mistermif_ai/packages
```

Se la configurazione esistente usa la forma standard
`packages: !include_dir_named packages`, Mistermif AI conserva quella struttura
e crea soltanto il file ponte `/config/packages/mistermif_ai.yaml`, che carica i
contenuti reali da `/config/mistermif_ai/packages`. Strutture diverse continuano
a richiedere verifica manuale. Ogni file creato nel workspace viene registrato e
inventariato.

## Sicurezza e autonomia

L'interruttore generale consente di fermare immediatamente tutte le azioni
operative. Quando è bloccato, osservazione, conversazione, diagnosi e notifiche
possono rimanere disponibili.

Mistermif AI può lavorare liberamente soltanto nella propria cartella. Qualsiasi
modifica esterna deve sempre essere spiegata e approvata singolarmente. Prima
della conferma deve indicare:

- motivo della modifica;
- file o configurazioni coinvolti;
- rischi ed effetti attesi;
- backup e procedura di ripristino.

Firmware, BMS, protezioni elettriche e parametri critici dell'inverter non fanno
parte dell'autoriparazione generale.

### Bozze di automazioni dinamiche

Il laboratorio genera e versiona bozze nel workspace dedicato, le simula con
dati virtuali e può osservarle in modalità ombra. Non le promuove da solo a
comandi reali. SBU, parametri inverter, BMS, firmware e ventilazione tecnica
restano sempre esclusi.

### Animali a bordo

Quando l'utente dichiara animali a bordo, l'impostazione viene conservata e il
comando autorizzato di spegnimento del clima viene bloccato. Lo stesso vincolo
viene applicato alle simulazioni energetiche.

Mistermif AI non sostituisce la supervisione umana né può essere considerato
l'unico sistema di protezione per persone o animali. Le soglie termiche urgenti,
gli allarmi locali e un percorso di intervento umano devono funzionare anche
senza AI o Internet.

Il contratto completo è in [`SECURITY.md`](SECURITY.md).

## Ricambi per caravan e camper

La ricerca assistita deve verificare costruttore, modello, anno, apparecchio,
codice componente, misure e connettori. Ogni risultato viene classificato come:

- compatibilità verificata dal produttore;
- equivalente documentato;
- candidato ancora da verificare.

Gas, freni, telaio, 230 V e dispositivi di sicurezza richiedono particolare
cautela e verifica professionale quando prevista. Nessun acquisto viene eseguito
automaticamente.

Ulteriori dettagli sono in [`docs/EXPERTISE.md`](docs/EXPERTISE.md).

## Installazione

> Prima dei test crea e conserva un backup completo di Home Assistant.

### Avvio rapido

1. Apri **Impostazioni → App → Store delle app**.
2. Apri il menu dei repository.
3. Aggiungi:

   ```text
   https://github.com/mistermif/mistermif-ai-apps
   ```

4. Aggiorna lo store e installa **mistermif AI**.
5. Avvia l'app e abilita **Mostra nella barra laterale**.
6. Rispondi alla breve intervista iniziale.
7. Premi **Attiva cartella dedicata** e conferma.

Per usare l'app in modalità locale non serve altro. Gemini, Groq e OpenAI sono
facoltativi. Le notifiche e le azioni automatiche si configurano in seguito.
L'autonomia rimane bloccata finché l'utente non la abilita.

### AI gratuita con Groq

1. Crea una chiave nel portale Groq e non inserirla mai nella repository.
2. In **Configurazione** seleziona `groq`.
3. Inserisci la chiave nel campo protetto `ai_api_key`.
4. Usa il modello `openai/gpt-oss-20b`.
5. Seleziona `redacted_cloud`, salva e riavvia solo l'app.

Le quote gratuite possono cambiare. Se Groq non risponde, memoria, monitoraggio,
apprendimento e protezioni locali continuano a funzionare.

Il piano gratuito pubblica limiti distinti per modello. Per
`openai/gpt-oss-20b` Groq indica attualmente fino a 30 richieste al minuto e
1.000 al giorno, oltre a limiti sui token; fanno fede i limiti mostrati nel
proprio account.

### OpenAI a consumo

OpenAI non dispone di un livello API gratuito per `gpt-5.4-mini`. L'API è
fatturata separatamente da ChatGPT e richiede credito o un metodo di pagamento.
Il modello indicato costa attualmente, per milione di token, 0,75 USD in input e
4,50 USD in output; eventuali strumenti hanno costi separati. Mistermif AI usa
OpenAI per le risposte, ma non abilita ancora automaticamente il Web Search di
OpenAI.

### Cosa fa automaticamente

- crea `/config/mistermif_ai` e le relative sottocartelle;
- salva una copia di `configuration.yaml` prima del collegamento;
- se non esiste una sezione `packages`, aggiunge l'include necessario;
- se esiste la forma comune `!include_dir_named packages`, crea il solo file
  ponte `/config/packages/mistermif_ai.yaml`;
- se trova una struttura personalizzata, non modifica nulla e mostra una
  spiegazione.

Non è necessario copiare file o scrivere YAML per le due configurazioni
standard sopra.

### Se qualcosa non parte

1. Apri la scheda **Registro** dell'app e cerca una riga `ERROR`.
2. Controlla che Home Assistant mostri l'app come **in esecuzione**.
3. Lascia l'autonomia bloccata finché il collegamento non è stabile.
4. In caso di errore `packages`, non modificare YAML alla cieca: consulta
   [`knaus_copilot/DOCS.md`](knaus_copilot/DOCS.md).

Il ripristino consiste nel fermare l'app, rimuovere il file ponte eventualmente
creato e recuperare la copia più recente da `/config/mistermif_ai/backup`.

## Documentazione e presentazione

- [Specifica funzionale del copilota 0.4](docs/COPILOT_04_SPEC.md)
- [Competenze viaggio e ricambi](docs/EXPERTISE.md)
- [Automazioni dinamiche e modalità animali a bordo](docs/DYNAMIC_AUTOMATIONS.md)
- [Ottimizzazione adattiva del frigorifero](docs/FRIDGE_OPTIMIZATION_SPEC.md)
- [Apprendimento locale e routine predittive](docs/LOCAL_LEARNING.md)
- [Privacy e conservazione locale](docs/PRIVACY.md)
- [Contratto di sicurezza](SECURITY.md)
- [Presentazione PowerPoint del progetto](outputs/mistermif-ai-presentazione.pptx)

## Privacy

Il repository non contiene token, password, indirizzi privati, coordinate GPS o
configurazioni personali di Home Assistant. Percorsi e coordinate sono dati
sensibili: restano nel database locale e vengono trasmessi soltanto quando
l'utente richiede esplicitamente un'esportazione CSV o GPX.

## Stato del progetto

Mistermif AI non è un dispositivo di sicurezza certificato. È una base funzionante sviluppata
per iterazioni controllate: ogni nuova capacità deve avere permessi espliciti,
test, registrazione delle decisioni e possibilità di disattivazione.
