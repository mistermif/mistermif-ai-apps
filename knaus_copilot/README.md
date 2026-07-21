# mistermif AI 0.7.0

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
- interruttore persistente Animali a bordo con protezione del clima;
- console essenziale con chat e due soli comandi permanenti;
- simulazioni energetiche descritte direttamente nella chat;
- autovalutazione locale del risultato e self-check completo;
- creazione isolata di plancia, helper, automazione fissa e policy dinamica;
- collaudo in simulazione e ombra prima di qualunque azione reale;
- blocco esplicito di batteria, inverter, ventilazione e firmware.

La modalità iniziale è `observe` con privacy `local_only`. Gemini, Groq e OpenAI
sono facoltativi. Con `contextual_cloud` l'utente può autorizzare posizione e
contesto Home Assistant utile; segreti, chiavi, token, password, IP e contatti
restano redatti anche quando presenti negli attributi annidati delle entità.
Le azioni operative richiedono autorizzazioni separate e
l'apprendimento non può modificare codice o parametri protetti.

Il profilo Gemini gratuito consigliato usa `gemini-3.5-flash`, Search
disattivato, 15 richieste giornaliere e 5 automatiche. Il piano gratuito non
include Google Search Grounding per questo modello; la funzione va attivata solo
su un progetto con fatturazione compatibile.
In caso di errore temporaneo `503`, l'app esegue brevi ritentativi e usa
automaticamente `gemini-3.1-flash-lite` come fallback gratuito.
Le richieste brevi vengono instradate sul modello Lite con ragionamento minimo;
le analisi complesse restano sul modello 3.5 e ricevono un contesto sensori
selezionato localmente.
I test rapidi non ricevono vecchi ricordi, mentre sensori offline o sconosciuti
vengono descritti come dati mancanti e non bastano, da soli, a generare
un'emergenza. Le indicazioni su pneumatici e TPMS separano dati verificati,
precauzioni e pericoli reali.

I test energetici non richiedono di scaricare realmente la batteria. Basta
scrivere, per esempio, `Simula batteria al 19%, senza sole e clima acceso` oppure
`Fai un test completo delle simulazioni energetiche`. Mistermif AI interpreta i
valori, esegue le regole e controlla da solo la coerenza; la lista delle azioni
eseguite resta sempre vuota. La modalità attiva è bloccata finché non sono
associati e convalidati i sensori reali in modalità ombra.

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
- `0.7`: uscita vocale opzionale.
