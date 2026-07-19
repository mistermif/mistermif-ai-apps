# Guida semplice a mistermif AI 0.3.3

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

## Chat OpenAI facoltativa

La modalità locale funziona senza chiave. Per attivare la conversazione cloud:

1. apri la scheda **Configurazione** dell'app;
2. inserisci la chiave OpenAI nel campo protetto;
3. seleziona `redacted_cloud`;
4. salva e riavvia l'app.

Non inserire mai la chiave nel repository, in `configuration.yaml`, nei log o in
una conversazione. Il filtro rimuove coordinate, tracker, reti, contatti e
memorie personali prima della richiesta al modello.

## Ripristino

1. Ferma mistermif AI.
2. Se presente, elimina `/config/packages/mistermif_ai.yaml`.
3. Recupera la copia desiderata da `/config/mistermif_ai/backup` solo se
   `configuration.yaml` era stato modificato direttamente.
4. Esegui il controllo della configurazione di Home Assistant prima del riavvio.

Database, intervista e conversazioni sono inclusi nel backup dell'app.
