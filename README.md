# mistermif AI

**mistermif AI** è un copilota intelligente per caravan basato su Home
Assistant. Unisce sensori, energia, GPS, meteo, memoria locale e conversazione
AI per spiegare cosa accade a bordo, inviare avvisi e coordinare esclusivamente
le azioni autorizzate.

Il progetto nasce su una caravan Knaus, ma l'architettura è pensata per essere
configurabile e adattabile ad altri camper e caravan.

> Il progetto è in sviluppo attivo. La versione corrente fornisce la base sicura
> del copilota; viaggio, campeggi, frigorifero e decisioni energetiche complete
> sono ancora in sviluppo progressivo.

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

## Cosa funziona oggi — versione 0.6.0

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
| `openai` | consumo a pagamento | non ancora collegata dall'app | qualità elevata; l'API è separata dall'abbonamento ChatGPT |

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

- **Emergenza:** intervento immediato, escalation e notifiche ripetute;
- **Urgenza:** intervento richiesto entro 10–15 minuti;
- **Allerta:** nessun intervento necessario, ma attenzione e monitoraggio.

I livelli descrivono priorità e tempi di risposta. Non sostituiscono protezioni
locali deterministiche per incendio, gas, temperatura, persone o animali.

### Intervista iniziale

Al primo avvio l'app chiede tipo, marca, modello e anno del mezzo. Per una
caravan richiede anche la motrice. Nomi e ruoli dell'equipaggio vengono
conservati esclusivamente nella memoria SQLite locale e sono esclusi dal
contesto cloud filtrato.

## Cosa è progettato per la 0.4

- profilo conversazionale del mezzo e dei suoi apparati;
- diario viaggi e contachilometri stimato dal GPS;
- rilevamento automatico di partenza, arrivo e sosta prolungata;
- riconoscimento di campeggi e aree dalle coordinate;
- memoria di piazzola, ampere, orientamento ed esposizione solare;
- preparazione del viaggio usando meteo ed esperienze precedenti;
- monitoraggio e analisi del frigorifero e delle sue ventole;
- integrazione TPMS opzionale per osservare pressione e temperatura degli
  pneumatici, rilevare tendenze e suggerire una sosta o una riduzione prudente
  della velocità senza sostituire le prescrizioni del costruttore;
- riepiloghi giornalieri di energia, temperature e comfort;
- allerte per vento, temporali, gelo, caldo e condensa;
- ricerca guidata di ricambi con verifica della compatibilità;
- autoriparazione limitata alla cartella dedicata, con test e ripristino.
- automazioni dinamiche contestuali create dall'assistente entro una lista di
  apparati, servizi e limiti autorizzati;
- modalità “animali a bordo” con climatizzazione prioritaria, previsione
  dell'autonomia ed escalation delle notifiche.
- apprendimento locale delle abitudini e preparazione predittiva delle risorse;
- modalità privacy locale predefinita, senza invio di dati al cloud.

La specifica dettagliata è disponibile in
[`docs/COPILOT_04_SPEC.md`](docs/COPILOT_04_SPEC.md).

## Architettura

```text
Sensori e automazioni Home Assistant
                 │
                 ▼
        filtro delle autorizzazioni
                 │
        ┌────────┴────────┐
        ▼                 ▼
 automazioni rapide   mistermif AI
 e deterministiche    ├─ chat
                      ├─ memoria locale
                      ├─ analisi e consigli
                      └─ azioni autorizzate
```

Solo il contesto necessario viene inviato al provider AI selezionato. Database,
memoria e file operativi restano locali, salvo esportazione richiesta
dall'utente. In
modalità predefinita `local_only` non viene inviato alcun contenuto al modello
cloud; la modalità `redacted_cloud` è opzionale e applica filtri preventivi.

## Apprendimento delle abitudini

Il copilota è progettato per riconoscere routine ripetute e preparare il mezzo.
Se, per esempio, la cucina a induzione viene usata spesso alle 12, può verificare
prima SOC, produzione, ricarica, limite della colonnina e carichi differibili.

Le abitudini non nascono da un singolo episodio. La versione 0.4.0 registra
campioni locali e li associa a un'identità anonima della sosta derivata da GPS e
orientamento. Campioni senza posizione non aumentano la confidenza e dati di
luoghi diversi non vengono mescolati.

L'apprendimento riguarda osservazioni e risultati: non modifica autonomamente
codice, firmware, soglie protette o parametri dell'impianto. L'utente potrà
correggere, sospendere e cancellare i dati appresi. Le decisioni energetiche
predittive complete verranno abilitate soltanto dopo simulazione storica e
modalità ombra.

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

### Automazioni dinamiche

Le automazioni create da Mistermif AI possono avere piena autonomia operativa
nel perimetro approvato. Non sono semplici soglie: considerano andamento della
batteria, produzione solare, ricarica esterna, orario, meteo, stato di viaggio,
temperature e priorità dichiarate dall'utente.

Per esempio, una regola “spegni il clima sotto il 30%” può attendere se la
batteria sta recuperando grazie al sole o a una fonte esterna, oppure intervenire
prima se è sera, la produzione è in calo e non sono previste altre fonti. I
vincoli rigidi di sicurezza restano deterministici e non possono essere rimossi
dal ragionamento AI.

Ogni automazione dinamica deve essere visibile, versionata, disattivabile,
registrare dati e motivazione di ogni decisione e offrire ripristino della
versione precedente. Nuovi apparati o nuove categorie di comando richiedono
approvazione esplicita.

Prima dell'attivazione ogni versione attraversa quattro fasi: bozza,
simulazione con dati virtuali, ombra con sensori reali ma zero comandi, e infine
attiva. Il passaggio alla fase attiva richiede interruttore generale abilitato,
associazione esplicita dei sensori e test superati. Il laboratorio non può
promuovere da solo comandi protetti come SBU, parametri inverter, BMS, firmware
o ventilazione tecnica.

### Animali a bordo

Quando l'utente dichiara animali a bordo, il clima diventa un carico prioritario
e non viene spento soltanto per risparmiare batteria. L'assistente deve stimare
in anticipo l'autonomia, usare sensori ridondanti, controllare che il clima stia
realmente funzionando e inviare avvisi progressivi prima che la situazione
diventi critica.

Mistermif AI non sostituisce la supervisione umana né può essere considerato
l'unico sistema di protezione per persone o animali. Le soglie termiche urgenti,
gli allarmi locali e un percorso di intervento umano devono funzionare anche
senza AI o Internet.

Il contratto completo è in [`SECURITY.md`](SECURITY.md).

## Campeggi, Park4night e memoria di viaggio

Il copilota è progettato per ricordare campeggi visitati, accessibilità,
corrente disponibile, servizi, piazzole, orientamento e strategie energetiche.

Park4night è previsto come fonte importante, ma non è stata individuata una API
pubblica per sviluppatori. L'integrazione verrà realizzata soltanto tramite API,
partnership o altra autorizzazione ufficiale. Sono esclusi scraping, elusione
dell'abbonamento e copia del database.

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
- [Apprendimento locale e routine predittive](docs/LOCAL_LEARNING.md)
- [Privacy e conservazione locale](docs/PRIVACY.md)
- [Contratto di sicurezza](SECURITY.md)
- [Presentazione PowerPoint del progetto](outputs/mistermif-ai-presentazione.pptx)

## Roadmap

- **0.1:** chat, memoria e lettura filtrata;
- **0.2:** primo controllo autorizzato del climatizzatore;
- **0.3:** workspace isolato, backup, manifest, kill switch e notifiche;
- **0.4:** viaggi, campeggi, meteo, frigorifero, energia e comfort;
- **0.5:** collegamento controllato con Codex sul Mac;
- **0.6:** voce opzionale attraverso l'impianto audio.

## Privacy

Il repository non contiene token, password, indirizzi privati, coordinate GPS o
configurazioni personali di Home Assistant. Percorsi e coordinate sono dati
sensibili: nella futura versione 0.4 resteranno locali e saranno esportabili o
cancellabili dall'utente.

## Stato del progetto

Mistermif AI non è ancora un prodotto finito. È una base funzionante sviluppata
per iterazioni controllate: ogni nuova capacità deve avere permessi espliciti,
test, registrazione delle decisioni e possibilità di disattivazione.
