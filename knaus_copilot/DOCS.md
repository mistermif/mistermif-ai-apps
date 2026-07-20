# Guida semplice a mistermif AI 0.5.2

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
memorie personali prima della richiesta al modello.

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
