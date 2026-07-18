# mistermif AI

**mistermif AI** è un copilota intelligente per caravan basato su Home
Assistant. Unisce sensori, energia, GPS, meteo, memoria locale e conversazione
AI per spiegare cosa accade a bordo, inviare avvisi e coordinare esclusivamente
le azioni autorizzate.

Il progetto nasce su una caravan Knaus, ma l'architettura è pensata per essere
configurabile e adattabile ad altri camper e caravan.

> Il progetto è in sviluppo attivo. La versione corrente fornisce la base sicura
> del copilota; viaggio, campeggi, frigorifero e analisi avanzate sono specificati
> per la versione 0.4 ma non sono ancora tutti operativi.

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

## Cosa funziona oggi — versione 0.3.1

- interfaccia web integrabile nella barra laterale di Home Assistant;
- chat OpenAI, quando viene configurata una chiave API;
- lettura filtrata delle entità Home Assistant autorizzate;
- memoria locale SQLite per conversazioni e note;
- workspace isolato sotto `/config/mistermif_ai`;
- backup controllato di `configuration.yaml` prima dell'inserimento dell'include;
- registro delle modifiche e inventario con hash SHA-256;
- interruttore persistente per bloccare il potere decisionale;
- spegnimento del solo climatizzatore configurato;
- notifiche tramite un servizio Home Assistant `notify.*` configurato;
- blocco di BMS, firmware, ventilazione inverter e parametri critici.

## Cosa è progettato per la 0.4

- profilo conversazionale del mezzo e dei suoi apparati;
- diario viaggi e contachilometri stimato dal GPS;
- rilevamento automatico di partenza, arrivo e sosta prolungata;
- riconoscimento di campeggi e aree dalle coordinate;
- memoria di piazzola, ampere, orientamento ed esposizione solare;
- preparazione del viaggio usando meteo ed esperienze precedenti;
- monitoraggio e analisi del frigorifero e delle sue ventole;
- riepiloghi giornalieri di energia, temperature e comfort;
- allerte per vento, temporali, gelo, caldo e condensa;
- ricerca guidata di ricambi con verifica della compatibilità;
- autoriparazione limitata alla cartella dedicata, con test e ripristino.
- automazioni dinamiche contestuali create dall'assistente entro una lista di
  apparati, servizi e limiti autorizzati;
- modalità “animali a bordo” con climatizzazione prioritaria, previsione
  dell'autonomia ed escalation delle notifiche.

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

Solo il contesto necessario viene inviato all'API OpenAI. Database, memoria e
file operativi restano locali, salvo esportazione richiesta dall'utente.

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

Se esiste già una configurazione `packages`, l'operazione si blocca. Ogni file
creato nel workspace viene registrato e inventariato.

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

1. Apri **Impostazioni → App → Store delle app**.
2. Apri il menu dei repository.
3. Aggiungi:

   ```text
   https://github.com/mistermif/mistermif-ai-apps
   ```

4. Aggiorna lo store e installa **mistermif AI**.
5. Configura la chiave OpenAI e le entità autorizzate.
6. Imposta il servizio `notify.*` desiderato.
7. Avvia l'app e abilita **Mostra nella barra laterale**.

## Documentazione e presentazione

- [Specifica funzionale del copilota 0.4](docs/COPILOT_04_SPEC.md)
- [Competenze viaggio e ricambi](docs/EXPERTISE.md)
- [Automazioni dinamiche e modalità animali a bordo](docs/DYNAMIC_AUTOMATIONS.md)
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
