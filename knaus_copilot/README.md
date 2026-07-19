# mistermif AI 0.3.3

App personale Home Assistant per supervisione, memoria e assistenza intelligente
della caravan.

- chat Ingress con memoria SQLite locale;
- lettura filtrata degli stati Home Assistant;
- intervista iniziale per mezzo, motrice ed equipaggio;
- livelli emergenza, urgenza e allerta;
- workspace isolato in `/config/mistermif_ai`;
- file ponte compatibile con un `/config/packages` già esistente;
- interruttore generale dell'autonomia;
- blocco esplicito di batteria, inverter, ventilazione e firmware.

La modalità iniziale è `observe` con privacy `local_only`. Il modello cloud e le
azioni operative richiedono configurazione e autorizzazioni separate.

## Sviluppo locale

```bash
cd knaus-copilot
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Installare la repo `https://github.com/mistermif/mistermif-ai-apps` dallo Store
delle app di Home Assistant.

## Roadmap

- `0.2`: monitor meteo e registro diagnostico;
- `0.3`: proposte di azione con conferma;
- `0.4`: strumenti Energy Pilot esplicitamente autorizzati;
- `0.5`: endpoint MCP per Codex sul Mac;
- `0.6`: uscita vocale opzionale.
