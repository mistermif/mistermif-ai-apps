# mistermif AI 0.5.2

App personale Home Assistant per supervisione, memoria e assistenza intelligente
della caravan.

- chat Ingress con memoria SQLite locale;
- provider locale, OpenAI, Groq e Gemini;
- Google Search opzionale per progetti Gemini compatibili, con citazioni;
- apprendimento energetico locale separato per contesto di sosta;
- lettura filtrata degli stati Home Assistant;
- intervista iniziale per mezzo, motrice ed equipaggio;
- livelli emergenza, urgenza e allerta;
- workspace isolato in `/config/mistermif_ai`;
- file ponte compatibile con un `/config/packages` già esistente;
- interruttore generale dell'autonomia;
- blocco esplicito di batteria, inverter, ventilazione e firmware.

La modalità iniziale è `observe` con privacy `local_only`. Gemini, Groq e OpenAI
sono facoltativi. Con `contextual_cloud` l'utente può autorizzare posizione e
contesto Home Assistant utile; segreti, chiavi, token, password, IP e contatti
restano redatti. Le azioni operative richiedono autorizzazioni separate e
l'apprendimento non può modificare codice o parametri protetti.

Il profilo Gemini gratuito consigliato usa `gemini-3.5-flash`, Search
disattivato, 15 richieste giornaliere e 5 automatiche. Il piano gratuito non
include Google Search Grounding per questo modello; la funzione va attivata solo
su un progetto con fatturazione compatibile.

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
