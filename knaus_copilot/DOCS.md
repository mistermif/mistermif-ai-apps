# Guida semplice a mistermif AI 0.7.1

## Installazione in cinque minuti

1. Crea un backup completo da **Impostazioni → Sistema → Backup**.
2. Aggiungi allo Store delle app il repository
   `https://github.com/mistermif/mistermif-ai-apps`.
3. Installa **mistermif AI**, attiva **Mostra nella barra laterale** e avvialo.
4. Rispondi all'intervista su mezzo, motrice ed equipaggio.
5. Premi **Attiva cartella dedicata** e conferma.

La configurazione iniziale è volutamente sicura:

- modalità `observe`;
- privacy `local_only`;
- potere decisionale bloccato;
- nessuna modifica a batteria, inverter, ventilazione o firmware.

## Cartella dedicata e packages

Tutto il lavoro dell'assistente resta in `/config/mistermif_ai`. Il collegamento
con Home Assistant è automatico nei casi comuni.

### Home Assistant senza packages

L'app salva una copia di `configuration.yaml` e aggiunge:

```yaml
homeassistant:
  packages: !include_dir_named mistermif_ai/packages
```

### Home Assistant con packages già configurati

Se trova:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

non cambia quella riga. Crea soltanto:

```text
/config/packages/mistermif_ai.yaml
```

Il file ponte carica i contenuti dalla cartella separata dell'assistente. Non
serve copiare o spostare automazioni.

### Configurazione personalizzata

Se `packages` usa un'altra forma, l'app si ferma senza salvare modifiche. Questo
non è un guasto: evita di rompere una configurazione esistente. Conserva il
messaggio mostrato e chiedi una verifica manuale.

## Intervista iniziale

Al primo avvio vengono chiesti:

- caravan o camper;
- marca, modello e anno;
- motrice, se il mezzo è una caravan;
- nomi e ruoli dell'equipaggio.

Il profilo resta nel database locale `/data/knaus_copilot.sqlite3`. Persone,
equipaggio, mezzo, viaggi e piazzole non vengono inclusi nel contesto cloud.

## Livelli degli avvisi

- **Emergenza:** intervento immediato.
- **Urgenza:** intervento entro 10–15 minuti.
- **Allerta:** nessun intervento richiesto, ma occorre prestare attenzione.

## I due interruttori

La schermata principale contiene soltanto la chat e due pulsanti permanenti:

- **Potere decisionale:** quando è attivo, Mistermif AI può usare senza altre
  conferme le azioni già autorizzate; quando è bloccato continua a osservare,
  ricordare, simulare e consigliare;
- **Animali a bordo:** quando è attivo il clima diventa prioritario. Mistermif AI
  applica automaticamente questa informazione alle simulazioni e rifiuta di
  spegnere il climatizzatore finché la modalità non viene disattivata.

Le protezioni su BMS, parametri inverter, firmware e ventilazione non vengono
rimosse dal pulsante del potere decisionale.

L'icona **⚙** apre le impostazioni con stato del collegamento, provider AI,
privacy, quote, apprendimento, profilo del mezzo, workspace e protezioni. Da qui
si può anche modificare il profilo iniziale e, se necessario, attivare la
cartella dedicata.

## Provare le automazioni senza scaricare la batteria

Apri la chat di mistermif AI e descrivi semplicemente la condizione. Per esempio:

```text
Simula batteria al 19%, senza sole, corrente -42 A e clima acceso.
```

Oppure chiedi:

```text
Fai un test completo di tutte le simulazioni energetiche.
```

L'assistente interpreta i dati, esegue la simulazione e controlla da solo se
decisione e protezioni sono coerenti. La risposta mostra dati virtuali,
decisione, motivo, azioni proposte, autoverifica ed eventuali assunzioni.

Il test non accende il clima, non cambia SBU/SUB, non usa la presa esterna e non
scarica la batteria. Scrive soltanto il risultato nel registro locale
`/config/mistermif_ai/log/energy_safety_lab.jsonl`.

I file tecnici eventualmente preparati restano separati:

- `packages/mistermif_ai_energy_lab.yaml`: helper virtuali caricabili da HA;
- `plance/energy_safety_lab.yaml`: plancia Lovelace pronta;
- `automazioni/energy_safety_lab_fixed.yaml`: descrizione della regola fissa;
- `automazioni/energy_safety_lab_dynamic_policy.yaml`: limiti dinamici;
- `laboratorio/energy_safety_lab.json`: manifest del laboratorio.

Se il collegamento `packages` è già attivo, Home Assistant vedrà i nuovi helper
dopo controllo della configurazione e riavvio. La simulazione nell'app funziona
subito anche con Home Assistant e sensori offline.

Ogni nuova logica segue:

1. **bozza** nella cartella dedicata;
2. **simulazione** con valori virtuali;
3. **ombra** con sensori reali, ma nessun comando;
4. **attiva** soltanto dopo convalida.

Un sensore `unknown` o `unavailable` rende la prova inconcludente e non può
generare un comando.

Per preparare in seguito la modalità ombra occorre associare:

- SOC batteria;
- potenza rete/PZEM;
- potenza solare;
- facoltativamente corrente batteria e climatizzatore;
- ampere disponibili.

Anche la prova in ombra registra soltanto ciò che l'assistente avrebbe deciso:
le azioni reali restano zero. La configurazione verrà guidata dalla chat e non è
più esposta come pannello tecnico nella schermata principale.

## AI facoltativa, anche gratuita

La modalità locale non richiede account, chiavi o pagamenti. Continua a
registrare dati, memorie e contesti di sosta anche senza un modello generativo.

### Gemini Free

1. crea una chiave in Google AI Studio senza attivare la fatturazione;
2. seleziona provider `gemini`;
3. inserisci la chiave in `ai_api_key`;
4. imposta `gemini-3.5-flash`;
5. lascia Google Search disattivato;
6. usa il profilo prudente 15 richieste totali / 5 automatiche;
7. salva e riavvia solo mistermif AI.

Il piano gratuito può ragionare sui dati forniti da Home Assistant, ma Gemini
3.5 Flash Free non include Google Search Grounding. Per ricerche aggiornate con
fonti occorre un progetto Gemini a pagamento e l'opzione Search attiva.

Se Gemini 3.5 Flash restituisce `503 Service Unavailable`, l'app ritenta
automaticamente e passa a `gemini-3.1-flash-lite`, anch'esso gratuito, quando
Search è disattivata. Non occorre cambiare la configurazione o la chiave.

La velocità è adattiva: domande brevi usano il modello Lite e ragionamento
minimo; domande normali usano ragionamento ridotto; analisi energetiche, meteo,
sicurezza e decisioni automatiche conservano il modello 3.5 e un ragionamento
più approfondito. Prima della richiesta cloud vengono scelti localmente solo i
sensori pertinenti, senza inviare inutilmente l'intero elenco di Home Assistant.
Saluti e semplici prove di connessione non ricevono vecchie memorie. Un sensore
`unavailable` o `unknown` rende la diagnosi incompleta, ma non costituisce da
solo una condizione di emergenza.

### Pneumatici e TPMS

Mistermif AI può aiutare a interpretare dati e tendenze, ma la pressione corretta
deve provenire dalla targhetta o dal manuale del mezzo e deve essere verificata
rispetto a misura, indice dello pneumatico e carico reale per asse. Una futura
integrazione TPMS potrà confrontare pressione e temperatura con velocità,
temperatura esterna e durata del viaggio, suggerendo una riduzione prudente
della velocità o una sosta quando i dati mostrano un'anomalia crescente.

### Groq Free

1. crea una chiave nel portale Groq;
2. apri **Configurazione** dell'app;
3. seleziona provider `groq`;
4. inserisci la chiave in `ai_api_key`;
5. imposta `openai/gpt-oss-20b`;
6. seleziona `redacted_cloud`;
7. salva e riavvia soltanto mistermif AI.

### OpenAI

È ancora supportato, ma richiede credito API separato dall'abbonamento ChatGPT.

### Confronto rapido

- `local`: nessun account, nessun costo, nessun dato al cloud;
- `gemini` Free: chat generativa gratuita entro la quota, senza ricerca Google;
- `groq` Free: chat rapida gratuita entro la quota, senza ricerca integrata;
- `gemini` Paid: ricerca Google con fonti e costi controllabili;
- `openai`: API a consumo separata da ChatGPT, senza quota gratuita garantita.

Non inserire mai la chiave nel repository, in `configuration.yaml`, nei log o in
una conversazione. Il filtro rimuove coordinate, tracker, reti, contatti e
memorie personali prima della richiesta al modello; controlla ricorsivamente
anche gli attributi annidati delle entità Home Assistant.

## Apprendimento locale

Ogni cinque minuti l'app registra localmente le misure energetiche autorizzate.
Lo storico di una sosta viene usato soltanto con GPS valido e viene separato per
area e orientamento. Una produzione registrata altrove non aumenta la confidenza
della posizione corrente.

L'app impara dati e risultati, non riscrive il proprio codice e non modifica
automaticamente inverter, batteria, ventilazione o firmware.

## Ripristino

1. Ferma mistermif AI.
2. Se presente, elimina `/config/packages/mistermif_ai.yaml`.
3. Recupera la copia desiderata da `/config/mistermif_ai/backup` solo se
   `configuration.yaml` era stato modificato direttamente.
4. Esegui il controllo della configurazione di Home Assistant prima del riavvio.

Database, intervista e conversazioni sono inclusi nel backup dell'app.
