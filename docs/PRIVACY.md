# Privacy e dati locali

## Impostazione predefinita

`privacy_mode: local_only` è la modalità predefinita. In questa modalità chat,
memoria, viaggi, coordinate, abitudini e profili non vengono inviati a un modello
cloud. Finché non sarà integrato un modello locale, le funzioni conversazionali
cloud restano disattivate.

## Cloud opzionale con redazione

`privacy_mode: redacted_cloud` deve essere scelto consapevolmente. Prima di una
richiesta esterna vengono rimossi o esclusi:

- coordinate e tracker;
- indirizzi IP e dati di rete;
- email, telefoni e token riconoscibili;
- memorie di viaggio, campeggio, piazzola, profilo, contatti e abitudini;
- entità Home Assistant legate a posizione o persone.

La redazione riduce il rischio ma non equivale alla garanzia matematica della
modalità locale. Testo libero e nuove forme di identificazione possono richiedere
nuove regole di filtro.

## Cloud contestuale

`privacy_mode: contextual_cloud` consente di includere posizione GPS, memorie di
viaggio, profilo del mezzo e stati Home Assistant autorizzati quando servono
alla richiesta. Anche in questa modalità vengono sempre rimossi chiavi API,
token, password, segreti, indirizzi IP, email e numeri di telefono.

Le chiamate sono limitate localmente da `cloud_daily_limit` e dal sotto-limite
`cloud_automatic_limit`. L'esaurimento del budget automatico non consuma la
riserva manuale e non ferma regole, memoria, apprendimento o automazioni locali.

## Conservazione

Database e file restano nei volumi locali dell'app e nella cartella dedicata.
Percorsi e coordinate devono supportare retention, esportazione, cancellazione
per viaggio e backup scelti dall'utente.

## Repository

Token, password, coordinate reali, indirizzi privati, database e configurazioni
personali non devono essere inseriti nel repository. Prima di ogni pubblicazione
si esegue un controllo di pattern sensibili e file non previsti.
