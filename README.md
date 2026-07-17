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

## Sicurezza della versione 0.1

La prima versione è intenzionalmente **sola lettura**:

- legge soltanto un insieme filtrato di stati Home Assistant;
- non monta la cartella `/config`;
- non chiama servizi e non esegue comandi;
- non modifica batteria, inverter, ventilazione, firmware o YAML;
- conserva chat e memorie nel volume privato `/data`;
- riceve la chiave OpenAI esclusivamente dalle opzioni protette dell'app.

Il repository non contiene token, password, indirizzi privati, coordinate GPS o
configurazioni personali di Home Assistant.

## Roadmap

- **0.1 — Osservazione:** chat, memoria e lettura filtrata degli stati.
- **0.2 — Diagnostica:** meteo, anomalie, sensori offline e registro eventi.
- **0.3 — Conferma:** proposte operative eseguibili solo dopo approvazione.
- **0.4 — Energia:** strumenti autorizzati per Energy Pilot e gestione dei carichi.
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
