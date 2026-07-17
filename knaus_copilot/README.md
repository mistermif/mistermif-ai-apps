# Knaus Copilot

Add-on personale Home Assistant per la supervisione intelligente della caravan.

La versione `0.1.0` è intenzionalmente **sola lettura**:

- chat tramite Ingress;
- memoria SQLite persistente;
- profili separati tramite identità Home Assistant;
- lettura filtrata degli stati;
- analisi AI con OpenAI Responses API;
- nessun comando verso Home Assistant.

## Sicurezza

L'add-on non monta `/config` e non possiede accesso al filesystem di Home
Assistant. Usa esclusivamente il proxy Core con `homeassistant_api: true`.
La classe `PermissionPolicy` filtra gli stati e nega ogni azione operativa.

I parametri di batteria, ventilazione, firmware e amministrazione sono
esplicitamente classificati come sensibili.

## Sviluppo locale

```bash
cd knaus-copilot
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Per provarlo su Home Assistant OS, copiare la cartella in:

```text
/addons/knaus_copilot
```

Poi aggiornare lo store degli add-on locali, installare e configurare la chiave
OpenAI dalla pagina dell'add-on.

## Roadmap

- `0.2`: monitor meteo e registro diagnostico;
- `0.3`: proposte di azione con conferma;
- `0.4`: strumenti Energy Pilot esplicitamente autorizzati;
- `0.5`: endpoint MCP per Codex sul Mac;
- `0.6`: uscita vocale opzionale.

