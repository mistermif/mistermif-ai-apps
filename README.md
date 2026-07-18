# mistermif AI

**mistermif AI** è un assistente intelligente locale per Home Assistant,
progettato inizialmente per una caravan con impianto energetico, sensori
ambientali, GPS, meteo e automazioni.

L'obiettivo non è sostituire le automazioni di sicurezza con decisioni
imprevedibili. Il progetto aggiunge un livello superiore capace di osservare,
ricordare, spiegare e, soltanto entro permessi espliciti, proporre o coordinare
azioni.

## Dove vogliamo arrivare

Il progetto vuole diventare un vero copilota digitale della caravan:

- controllare lo stato generale di energia, batteria, inverter e climatizzazione;
- individuare dati incoerenti, sensori offline e comportamenti anomali;
- seguire meteo e posizione GPS e segnalare condizioni importanti;
- ricordare richieste, preferenze, interventi e recensioni dei campeggi;
- riconoscere campeggi già visitati e ricordarne corrente disponibile, servizi,
  accessibilità, note personali e strategie energetiche usate;
- assistere nella ricerca di ricambi verificando modello, anno, codice componente
  e compatibilità prima di proporre l'acquisto;
- spiegare in linguaggio naturale cosa sta accadendo e perché;
- dialogare attraverso una chat integrata in Home Assistant;
- comunicare con Codex sul Mac tramite un'interfaccia controllata;
- in futuro, parlare attraverso l'impianto audio della caravan;
- proporre azioni e attuarle solo quando la politica di autorizzazione lo permette.

Le automazioni locali continueranno a gestire le reazioni rapide e deterministiche,
come protezioni elettriche e termiche. L'AI si occuperà di supervisione, contesto,
diagnostica e assistenza.

## Come funziona

```text
Sensori e automazioni Home Assistant
                │
                ▼
       filtro delle autorizzazioni
                │
                ▼
           mistermif AI
       ┌────────┼─────────┐
       ▼        ▼         ▼
     chat     memoria   analisi AI
```

La memoria è conservata localmente in SQLite nel volume privato dell'app. Solo il
contesto filtrato necessario alla conversazione viene inviato all'API OpenAI.

## Workspace isolato

Ogni file creato o modificato dall'assistente viene conservato sotto:

```text
/config/mistermif_ai/
├── packages/
├── plance/
├── automazioni/
├── script/
├── template/
├── helper/
├── backup/
├── log/
└── manifest/
```

L'assistente non può scrivere fuori da questa cartella. Prima di collegare il
workspace crea una copia di `configuration.yaml`; nel file centrale aggiunge
soltanto:

```yaml
homeassistant:
  packages: !include_dir_named mistermif_ai/packages
```

Se esiste già una configurazione `packages`, l'operazione si blocca e richiede
un intervento manuale. Ogni scrittura viene registrata in `log/changes.jsonl` e
inventariata con hash SHA-256 in `manifest/files.json`.

## Sicurezza e autonomia

La modalità predefinita resta **sola lettura**. Dalla versione 0.2 è disponibile
un primo comando strettamente autorizzato:

- legge soltanto un insieme filtrato di stati Home Assistant;
- non monta la cartella `/config`;
- può spegnere soltanto l'entità climatizzatore configurata;
- in modalità `confirm` richiede una conferma nell'interfaccia;
- in modalità `limited` può eseguire lo spegnimento richiesto direttamente;
- non modifica batteria, inverter, ventilazione, firmware o YAML;
- conserva chat e memorie nel volume privato `/data`;
- riceve la chiave OpenAI esclusivamente dalle opzioni protette dell'app.

Il repository non contiene token, password, indirizzi privati, coordinate GPS o
configurazioni personali di Home Assistant.

## Roadmap

- **0.1 — Osservazione:** chat, memoria e lettura filtrata degli stati.
- **0.2 — Controllo limitato:** spegnimento autorizzato del climatizzatore.
- **0.3 — Workspace isolato:** include controllato, backup, log e manifest.
- **0.3.x — Diagnostica:** meteo, anomalie, sensori offline e registro eventi.
- **0.3 — Conferma:** proposte operative eseguibili solo dopo approvazione.
- **0.4 — Energia:** strumenti autorizzati per Energy Pilot e gestione dei carichi.
- **0.4.x — Viaggi:** memoria campeggi, GPS, meteo, preferenze e schede di sosta.
- **0.4.x — Park4night:** connettore ufficiale subordinato alla disponibilità di
  API o autorizzazione del fornitore; nessuno scraping o aggiramento dell'account.
- **0.4.x — Ricambi:** ricerca assistita su cataloghi ufficiali, archivio dei
  componenti installati e verifica guidata della compatibilità.
- **0.5 — Collegamento Mac:** interfaccia controllata per Codex.
- **0.6 — Voce opzionale:** notifiche vocali attraverso l'audio della caravan.

I parametri critici di batteria, inverter, ventilazione e firmware resteranno
esclusi dall'autonomia generale e richiederanno sempre procedure dedicate.

## Installazione

> La versione 0.1 è destinata a test controllati. Crea prima un backup completo
> di Home Assistant.

1. Apri **Impostazioni → App → Store delle app** in Home Assistant.
2. Apri il menu dei repository.
3. Aggiungi:

   ```text
   https://github.com/mistermif/mistermif-ai-apps
   ```

4. Aggiorna lo store e installa **mistermif AI**.
5. Inserisci la chiave OpenAI API nella configurazione dell'app.
6. Avvia l'app e abilita **Mostra nella barra laterale**.

## Stato del progetto

Il progetto è in sviluppo attivo. Le funzionalità operative verranno aggiunte
gradualmente, accompagnate da permessi espliciti, test e possibilità di
disattivazione.

### Integrazione Park4night

Park4night è previsto come fonte importante per campeggi e aree attrezzate. Il
sito offre ricerca delle soste, coordinate e funzioni avanzate con Park4night+,
ma al momento non è stata individuata una API pubblica per sviluppatori. Il
progetto implementerà quindi soltanto un collegamento autorizzato dal fornitore.
Fino ad allora mistermif AI potrà conservare localmente schede e recensioni
personali, aprire collegamenti Park4night e analizzare le informazioni fornite
dall'utente senza replicare il loro database.
