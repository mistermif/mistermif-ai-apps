# mistermif AI 1.2.0

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
- ponte consultivo di laboratorio/MCP autenticato per stato, simulazioni e proposte;
- gemello digitale sul Mac senza servizi Home Assistant eseguibili dal ponte.
- scheda grafica per simulazioni e self-check, più diagramma del ponte nelle
  impostazioni.
- sorveglianza meteo autonoma ogni 30 minuti senza consumo di token AI;
- fusione locale di sensori HA, Open-Meteo multimodello e Radar-DPC grandine;
- andamento di barometro, temperatura e umidità esterna registrato localmente;
- revisione Gemini solo per nuovi rischi o peggioramenti, massimo 10 al giorno;
- avvisi persistenti e deduplicati, con Telegram per urgenze ed emergenze;
- diario viaggi GPS automatico con soste, velocità, distanza, report, CSV e GPX.
- scoperta automatica dei componenti del frigorifero con richiesta in chat;
- ottimizzazione vincolata dei parametri ESPHome giorno/notte oppure controllo
  PWM diretto negli impianti semplici, sempre con blocco generale.
- modalità persistente di sola osservazione e suggerimenti, valida anche con
  configurazione incompleta e senza alcun comando Home Assistant.
- fallback semantico Gemini per comprendere istruzioni contestuali ambigue,
  senza trasformare l'interpretazione del modello in autorizzazione operativa.

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

## Configurare meteo e viaggi

Le impostazioni predefinite attivano il meteo ogni 30 minuti e il GPS ogni 30
secondi. `telegram_targets` accetta gli ID chat separati da virgola. Windy è
opzionale e richiede una chiave Point Forecast Professional; la chiave gratuita
di test non è adatta a dati reali. `travel_arrival_minutes` stabilisce dopo
quanto tempo una sosta chiude automaticamente il viaggio (predefinito 120).

Le decisioni meteo sono regole locali e consumano zero richieste Gemini,
OpenAI o Groq quando il quadro è sereno o stabile. Se `weather_ai_enabled` è
attivo, un nuovo rischio può richiedere una singola revisione Gemini. Il limite
`weather_ai_daily_limit` non può superare 10. Open-Meteo e Radar-DPC sono
richieste dati normali, non token AI.

## Ventilazione frigorifero

L'app individua le entità compatibili, notifica l'utente e raccoglie in chat
marca, modello, sonda radiatore superiore, temperatura esterna, temperatura
interna e comando PWM. Senza tutti i dati e la frase esplicita di autorizzazione
resta in osservazione. L'autorizzazione vale soltanto per l'entity ID confermato
e non include mai le ventole dell'inverter.

Se trova temperatura iniziale, temperatura PWM 100, velocità iniziale e
isteresi per giorno e notte, conserva la logica rapida sull'ESP e ne affina i
parametri al massimo ogni sei ore. Se trova soltanto un comando PWM, applica
direttamente una curva progressiva con 100% a 40 °C. Dopo una cronologia locale
sufficiente rende la strategia più aggressiva quando la temperatura interna non
rimane stabile.
