# Knaus Copilot Apps

Repository pubblico per le app Home Assistant del progetto Knaus Copilot.

## Installazione

1. Apri **Impostazioni → App → Store delle app** in Home Assistant.
2. Apri il menu dei repository.
3. Aggiungi:

   ```text
   https://github.com/mistermif/knaus-copilot-apps
   ```

4. Aggiorna lo store e installa **Knaus Copilot**.
5. Inserisci la chiave OpenAI API nella configurazione dell'app.
6. Avvia l'app e abilita **Mostra nella barra laterale**.

## Sicurezza della versione 0.1

La prima versione è intenzionalmente osservativa:

- legge soltanto un insieme filtrato di stati Home Assistant;
- non monta la cartella `/config`;
- non chiama servizi e non esegue comandi;
- non modifica batteria, inverter, ventilazione, firmware o YAML;
- conserva chat e memorie nel volume privato `/data` dell'app;
- riceve la chiave OpenAI esclusivamente dalle opzioni protette dell'app.

Il repository non contiene token, password, indirizzi privati, coordinate GPS o
configurazioni personali di Home Assistant.

## Stato

Versione iniziale destinata a test controllati su Home Assistant OS. Prima
dell'installazione è consigliato creare un backup completo.

