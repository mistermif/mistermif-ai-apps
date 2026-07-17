# Knaus Copilot 0.1

## Installazione futura

1. Creare e scaricare un backup completo di Home Assistant.
2. Copiare `knaus-copilot` in `/addons/knaus_copilot`.
3. Aprire **Impostazioni → Add-on → Store degli add-on**.
4. Dal menu, scegliere **Controlla aggiornamenti**.
5. Aprire **Add-on locali → Knaus Copilot** e installare.
6. Nella configurazione inserire la chiave OpenAI API.
7. Avviare l'add-on e abilitare **Mostra nella barra laterale**.

La chiave OpenAI viene memorizzata nelle opzioni protette dell'add-on. Non deve
essere scritta nei file YAML di Home Assistant o nel repository Git.

## Comportamento della versione 0.1

Knaus Copilot può leggere un insieme limitato di entità e costruire un contesto
per la conversazione. Non può chiamare servizi Home Assistant.

La modalità `observe`, `confirm` o `limited` è già presente nell'interfaccia di
configurazione, ma nella versione 0.1 tutte e tre rimangono in sola lettura. La
differenza verrà attivata soltanto nelle versioni successive.

## Memoria

Il database si trova in `/data/knaus_copilot.sqlite3` ed è incluso nei backup
dell'add-on. Le memorie possono essere private per utente oppure condivise.

## Dati mancanti

Se Home Assistant non è raggiungibile o la chiave OpenAI non è configurata,
l'interfaccia continua ad avviarsi e mostra chiaramente la modalità di
preparazione.

