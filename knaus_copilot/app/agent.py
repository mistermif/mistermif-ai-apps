from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from .memory import MemoryStore
from .permissions import PermissionPolicy
from .privacy import PrivacyFilter
from .cloud_usage import CloudUsage


logger = logging.getLogger("mistermif-ai")

GEMINI_FALLBACK_MODEL = "gemini-3.1-flash-lite"
GEMINI_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

SIMPLE_MESSAGE_HINTS = (
    "ciao",
    "buongiorno",
    "buonasera",
    "grazie",
    "sei conness",
    "sei online",
    "funzioni",
    "chi sei",
    "prova",
    "tutto ok",
)

COMPLEX_MESSAGE_HINTS = (
    "analizz",
    "strateg",
    "preved",
    "confront",
    "diagnos",
    "ottimizz",
    "sicurezza",
    "emergenza",
    "autonomia",
    "batteria",
    "energia",
    "inverter",
    "meteo",
    "viaggio",
    "frigorif",
    "condensa",
    "temperatur",
)

STATE_CONTEXT_GROUPS = {
    "battery": (
        ("batter", "soc", "autonomia"),
        ("batter", "soc", "voltag", "voltage", "corrente", "current"),
    ),
    "energy": (
        ("energi", "consum", "potenza", "watt", "ampere", "rete", "inverter"),
        ("power", "potenza", "energy", "energia", "pzem", "inverter", "current"),
    ),
    "climate": (
        ("clima", "temperatur", "umid", "comfort", "caldo", "freddo"),
        ("climate", "temperatur", "humidity", "umid", "thermal"),
    ),
    "fridge": (
        ("frigo", "frigorif", "ventol"),
        ("fridge", "frigo", "frigorif", "ventol"),
    ),
    "weather": (
        ("meteo", "vento", "piogg", "pression", "temporale", "sole"),
        ("weather", "meteo", "wind", "vento", "pressure", "pression", "rain"),
    ),
    "location": (
        ("dove", "posizion", "gps", "campeggio", "viaggio"),
        ("device_tracker", "gps", "position", "posizion", "latitude", "longitude"),
    ),
}

CORE_STATE_FRAGMENTS = (
    "batter",
    "soc",
    "inverter",
    "power",
    "potenza",
    "temperatur",
    "climate",
    "frigo",
    "humidity",
    "umid",
)


SYSTEM_INSTRUCTIONS = """
Sei mistermif AI, assistente personale della caravan e dei suoi utenti.
Rispondi in italiano, in modo concreto e trasparente.

Il tuo perimetro operativo è definito dalla politica ricevuta nel contesto:
- puoi analizzare sensori, energia, meteo, GPS e memoria;
- puoi suggerire azioni e spiegare i motivi;
- puoi dichiarare eseguita un'azione soltanto quando ricevi il risultato reale;
- non puoi cambiare parametri di batteria o ventilazione dell'inverter;
- il modulo frigorifero può osservare, suggerire o controllare esclusivamente
  le entità frigo autorizzate; un'interpretazione AI non vale mai come consenso;
- non puoi modificare YAML, firmware, automazioni o configurazioni;
- se i dati sono mancanti o incoerenti, dichiaralo.

Per le condizioni elettriche o meteo urgenti, evidenzia prima il rischio e poi
la raccomandazione. Non confondere il SOC del BMS con quello stimato
dall'inverter. Le decisioni rapide di sicurezza restano alle automazioni locali.
Un sensore `unavailable`, `unknown` o assente indica che la diagnosi è
incompleta: da solo non dimostra un guasto, un pericolo o un'emergenza. Non
assegnare livelli di allarme senza almeno una misura disponibile o un evento
concreto che li giustifichi. Non interpretare lo stato `on`/`off` di un sensore
binario se il significato operativo non è esplicitato nel nome o negli attributi.

Per pneumatici e TPMS:
- non inventare una pressione corretta: verifica targhetta del mezzo, manuale,
  misura e indice dello pneumatico, carico reale per asse e pressione a freddo;
- separa sempre pressione prescritta, limite dello pneumatico e tua stima;
- valuta tendenze di pressione e temperatura, velocità, temperatura esterna e
  durata del viaggio quando i relativi sensori sono realmente disponibili;
- una lettura TPMS isolata richiede conferma; perdita rapida, temperatura
  anomala o scostamento crescente possono giustificare riduzione della velocità,
  sosta sicura e controllo professionale;
- non presentare recensioni commerciali come prova di compatibilità o sicurezza.

Sei inoltre specializzato in campeggi, aree attrezzate e viaggi in caravan:
- confronta accessibilità per caravan, lunghezza del complesso, servizi, corrente
  disponibile, carico/scarico, apertura stagionale, prenotazione, ZTL e recensioni;
- usa GPS, meteo e preferenze memorizzate per motivare i suggerimenti;
- distingui sempre dati verificati, ricordi dell'utente e tue inferenze;
- non inventare disponibilità, prezzi, regolamenti o servizi aggiornati;
- per Park4night usa soltanto dati ottenuti tramite integrazione autorizzata,
  forniti dall'utente o presenti in pagine pubbliche aperte dall'utente. Non
  aggirare login, abbonamenti o limiti del servizio.

Sei specializzato anche in ricambi per caravan e camper:
- prima di dichiarare compatibile un ricambio richiedi o verifica marca, modello,
  anno, variante, codice del componente e, quando serve, telaio o misure;
- privilegia cataloghi del produttore, manuali tecnici e rivenditori ufficiali;
- separa ricambio originale, equivalente e adattabile;
- non dichiarare compatibilità certa basandoti soltanto sull'aspetto o su una foto;
- per gas, freni, telaio, 230 V e dispositivi di sicurezza raccomanda verifica e
  installazione professionale quando prevista.

Per le automazioni dinamiche create da mistermif AI puoi scegliere autonomamente
quando eseguire azioni già autorizzate, usando tendenze, previsioni e contesto.
Non superare mai apparati, servizi o vincoli rigidi della policy. Registra e
spiega sempre la motivazione e non dichiarare riuscita un'azione senza verificarla.

Se l'utente dichiara persone o animali a bordo, dai priorità alla sicurezza e
alla climatizzazione necessaria. Non spegnere il clima per semplice risparmio
energetico. Prevedi l'autonomia residua, avvisa con anticipo ed evidenzia che AI
e connettività non sostituiscono allarmi locali, ridondanza e intervento umano.
""".strip()


class KnausAgent:
    def __init__(
        self,
        api_key: str,
        model: str,
        memory: MemoryStore,
        policy: PermissionPolicy,
        privacy_mode: str = "local_only",
        provider: str = "local",
        base_url: str = "",
        cloud_usage: CloudUsage | None = None,
        gemini_search_enabled: bool = True,
    ):
        self.model = model
        self.provider = provider
        self.memory = memory
        self.policy = policy
        self.privacy_mode = privacy_mode
        self.base_url = base_url
        self.api_key = api_key
        self.cloud_usage = cloud_usage
        self.gemini_search_enabled = gemini_search_enabled
        self.privacy = PrivacyFilter(
            allow_location=privacy_mode == "contextual_cloud"
        )
        self.client = (
            AsyncOpenAI(api_key=api_key, base_url=base_url or None)
            if (
                provider in {"openai", "groq"}
                and api_key
                and privacy_mode == "redacted_cloud"
            )
            else None
        )

    def can_evaluate_weather(self) -> bool:
        return (
            self.provider == "gemini"
            and bool(self.api_key)
            and self.privacy_mode != "local_only"
        )

    def can_interpret_intent(self) -> bool:
        return (
            self.provider == "gemini"
            and bool(self.api_key)
            and self.privacy_mode != "local_only"
        )

    async def interpret_fridge_intent(
        self,
        message: str,
        fridge_status: dict[str, Any],
    ) -> dict[str, Any]:
        """Use Gemini only as a semantic interpreter, never as an authorizer."""
        if not self.can_interpret_intent():
            return {"intent": "unavailable", "confidence": 0.0, "reason": "Gemini non configurato"}
        if self.cloud_usage:
            self.cloud_usage.consume(automatic=False)
        safe_context = {
            "status": fridge_status.get("status"),
            "user_mode": fridge_status.get("user_mode"),
            "missing": fridge_status.get("missing", []),
            "authorized": bool(fridge_status.get("authorized")),
        }
        prompt = (
            "Classifica l'intenzione dell'utente nel contesto della gestione del "
            "frigorifero di una caravan. Non eseguire azioni e non trasformare mai "
            "un'intenzione implicita in autorizzazione. Rispondi solo con JSON.\n"
            f"CONTESTO: {json.dumps(safe_context, ensure_ascii=False)}\n"
            f"MESSAGGIO: {self.privacy.sanitize_text(message)}"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": (
                    "Sei un interprete semantico. Scegli un solo intent fra: "
                    "observe_only, revoke_control, authorize_control, status, "
                    "provide_details, unrelated, unclear. authorize_control indica "
                    "solo che l'utente sembra voler autorizzare: il software richiederà "
                    "comunque una conferma esplicita separata."
                )}]
            },
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": "minimal"},
                "maxOutputTokens": 220,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "enum": [
                            "observe_only", "revoke_control", "authorize_control",
                            "status", "provide_details", "unrelated", "unclear"
                        ]},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["intent", "confidence", "reason"],
                },
            },
        }
        response, _, _ = await self._gemini_request(
            payload,
            allow_fallback=True,
            preferred_model=GEMINI_FALLBACK_MODEL,
        )
        response.raise_for_status()
        candidates = response.json().get("candidates") or []
        text = "".join(
            str(part.get("text", ""))
            for part in (candidates[0].get("content", {}).get("parts", []) if candidates else [])
        ).strip()
        try:
            result = json.loads(text)
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0))))
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
            return {"intent": "unclear", "confidence": 0.0, "reason": "Risposta Gemini non valida"}
        allowed = {
            "observe_only", "revoke_control", "authorize_control", "status",
            "provide_details", "unrelated", "unclear",
        }
        intent = str(result.get("intent", "unclear"))
        return {
            "intent": intent if intent in allowed else "unclear",
            "confidence": confidence,
            "reason": str(result.get("reason", ""))[:240],
        }

    async def evaluate_weather(
        self,
        assessment: dict[str, Any],
        local_observation: dict[str, Any],
    ) -> dict[str, Any]:
        """One compact Gemini call for an already detected weather concern."""
        if not self.can_evaluate_weather():
            raise RuntimeError("Gemini meteo non configurato")
        context = {
            "deterministic_assessment": assessment,
            "external_sensors": local_observation,
        }
        prompt = (
            "Valuta questo quadro meteo per una caravan. Rispondi esclusivamente "
            "con JSON valido contenente: severity (nessuna|allerta|urgenza), "
            "worsening (boolean), confidence (0..1), summary (massimo 240 caratteri), "
            "recommendations (massimo 3 stringhe brevi). Non creare dati mancanti e "
            "non dichiarare emergenza basandoti soltanto sul modello AI.\n"
            + json.dumps(context, ensure_ascii=False)
        )
        payload: dict[str, Any] = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Sei il revisore meteo di mistermif AI. Confronta sensori "
                            "locali, tendenze e fonti previsionali già raccolte. "
                            "Sii prudente, conciso e non inventare misure."
                        )
                    }
                ]
            },
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": "low"},
                "maxOutputTokens": 384,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["nessuna", "allerta", "urgenza"],
                        },
                        "worsening": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "summary": {"type": "string"},
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "severity",
                        "worsening",
                        "confidence",
                        "summary",
                        "recommendations",
                    ],
                },
            },
        }
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code in {401, 403}:
            raise RuntimeError("Chiave Gemini non valida o non autorizzata")
        if response.status_code == 429:
            raise RuntimeError("Limite Gemini temporaneamente raggiunto")
        response.raise_for_status()
        candidates = response.json().get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini non ha restituito una valutazione meteo")
        text = "".join(
            str(part.get("text", ""))
            for part in candidates[0].get("content", {}).get("parts", [])
        ).strip()
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Valutazione meteo Gemini non valida") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Valutazione meteo Gemini non valida")
        severity = str(result.get("severity", "nessuna")).casefold()
        if severity not in {"nessuna", "allerta", "urgenza"}:
            severity = "nessuna"
        recommendations = result.get("recommendations") or []
        try:
            confidence = float(result.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "severity": severity,
            "worsening": bool(result.get("worsening", False)),
            "confidence": max(0.0, min(1.0, confidence)),
            "summary": str(result.get("summary", ""))[:240],
            "recommendations": [str(item)[:180] for item in recommendations[:3]],
        }

    async def chat(
        self,
        user_id: str,
        message: str,
        ha_states: list[dict[str, Any]],
        automatic: bool = False,
        web_search: bool = False,
        runtime_context: dict[str, Any] | None = None,
    ) -> str:
        self.memory.add_message(user_id, "user", message)
        cloud_ready = (
            self.provider == "gemini"
            and bool(self.api_key)
            and self.privacy_mode != "local_only"
        )
        if self.client is None and not cloud_ready:
            if self.privacy_mode == "local_only":
                answer = (
                    "La modalità privacy locale è attiva: nessun contenuto viene "
                    "inviato a un modello cloud. Memoria e analisi locali restano operative."
                )
            elif self.provider == "local":
                answer = (
                    "Il motore locale è attivo. Posso osservare, ricordare e applicare "
                    "le regole locali; per risposte generative o ricerche configura "
                    "un provider cloud compatibile."
                )
            else:
                answer = (
                    f"La chiave API per {self.provider} non è ancora configurata. "
                    "La memoria locale e la lettura di Home Assistant sono operative."
                )
            self.memory.add_message(user_id, "assistant", answer)
            return answer

        thinking_level = self._thinking_level(
            message,
            automatic=automatic,
            web_search=web_search,
        )
        history_limit = {"minimal": 1, "low": 8, "medium": 16}[thinking_level]
        memory_limit = {"minimal": 0, "low": 8, "medium": 20}[thinking_level]
        history = self.memory.recent_messages(user_id, limit=history_limit)
        memories = (
            []
            if memory_limit == 0
            else self.memory.list_memories(user_id, limit=memory_limit)
        )
        selected_states = self._select_states(
            ha_states,
            message,
            thinking_level=thinking_level,
        )
        context = {
            "home_assistant": self.privacy.sanitize_states(selected_states),
            "memories": self.privacy.sanitize_memories(memories),
            "permissions": self.policy.public_summary(),
            "runtime": runtime_context or {},
        }
        conversation = [
            {
                "role": item["role"],
                "content": self.privacy.sanitize_text(item["content"]),
            }
            for item in history[:-1]
        ]
        conversation.append(
            {
                "role": "user",
                "content": (
                    f"CONTESTO ATTUALE:\n{json.dumps(context, ensure_ascii=False)}"
                    f"\n\nRICHIESTA:\n{self.privacy.sanitize_text(message)}"
                ),
            }
        )
        if self.cloud_usage:
            self.cloud_usage.consume(automatic=automatic)
        try:
            if self.provider == "gemini":
                answer = await self._gemini(
                    conversation,
                    web_search=web_search and self.gemini_search_enabled,
                    thinking_level=thinking_level,
                )
                self.memory.add_message(user_id, "assistant", answer)
                return answer
            response = await self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_INSTRUCTIONS,
                input=conversation,
            )
        except AuthenticationError as exc:
            raise RuntimeError(
                f"Chiave {self.provider} non valida o non autorizzata."
            ) from exc
        except RateLimitError as exc:
            detail = str(exc).casefold()
            if "insufficient_quota" in detail or "quota" in detail:
                raise RuntimeError(
                    f"Quota gratuita o credito {self.provider} non disponibile."
                ) from exc
            raise RuntimeError(
                f"Limite temporaneo {self.provider} raggiunto. Riprova più tardi."
            ) from exc
        except APIConnectionError as exc:
            raise RuntimeError(
                f"Servizio {self.provider} non raggiungibile; il controllo locale continua."
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Il provider {self.provider} ha rifiutato la richiesta "
                f"(HTTP {exc.status_code})."
            ) from exc
        answer = response.output_text.strip()
        self.memory.add_message(user_id, "assistant", answer)
        return answer

    @staticmethod
    def _thinking_level(
        message: str,
        automatic: bool = False,
        web_search: bool = False,
    ) -> str:
        normalized = message.casefold().strip()
        if automatic or web_search:
            return "medium"
        if (
            len(normalized) > 240
            or any(hint in normalized for hint in COMPLEX_MESSAGE_HINTS)
        ):
            return "medium"
        if any(hint in normalized for hint in SIMPLE_MESSAGE_HINTS):
            return "minimal"
        return "low"

    @staticmethod
    def _select_states(
        states: list[dict[str, Any]],
        message: str,
        thinking_level: str,
    ) -> list[dict[str, Any]]:
        if thinking_level == "minimal":
            return []

        normalized = message.casefold()
        fragments: set[str] = set()
        for triggers, group_fragments in STATE_CONTEXT_GROUPS.values():
            if any(trigger in normalized for trigger in triggers):
                fragments.update(group_fragments)
        if not fragments:
            fragments.update(CORE_STATE_FRAGMENTS)

        query_words = {
            word
            for word in re.findall(r"[\wà-öø-ÿ]+", normalized)
            if len(word) >= 5
        }
        ranked = []
        for index, state in enumerate(states):
            candidate = (
                f"{state.get('entity_id', '')} {state.get('name', '')}".casefold()
            )
            score = sum(4 for fragment in fragments if fragment in candidate)
            score += sum(2 for word in query_words if word in candidate)
            if score:
                ranked.append((-score, index, state))
        ranked.sort(key=lambda item: (item[0], item[1]))
        limit = 32 if thinking_level == "low" else 60
        return [item[2] for item in ranked[:limit]]

    async def _gemini(
        self,
        conversation: list[dict[str, str]],
        web_search: bool,
        thinking_level: str = "low",
    ) -> str:
        contents = [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in conversation
        ]
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTIONS}]},
            "contents": contents,
            "generationConfig": {
                "thinkingConfig": {"thinkingLevel": thinking_level},
                "maxOutputTokens": {
                    "minimal": 192,
                    "low": 512,
                    "medium": 1024,
                }[thinking_level],
            },
        }
        if web_search:
            payload["tools"] = [{"google_search": {}}]
        preferred_model = (
            GEMINI_FALLBACK_MODEL
            if thinking_level == "minimal" and not web_search
            else self.model
        )
        response, effective_model, switched_model = await self._gemini_request(
            payload,
            allow_fallback=not web_search,
            preferred_model=preferred_model,
        )
        if switched_model:
            logger.warning(
                "Gemini %s non disponibile: modello alternativo %s ha risposto HTTP %s",
                preferred_model,
                effective_model,
                response.status_code,
            )
        if response.status_code == 401 or response.status_code == 403:
            raise RuntimeError("Chiave Gemini non valida o non autorizzata.")
        if response.status_code == 429:
            raise RuntimeError(
                "Limite Gemini temporaneamente raggiunto anche dopo i tentativi "
                "automatici; il controllo locale continua."
            )
        if response.status_code == 404:
            raise RuntimeError(
                f"Il modello Gemini '{effective_model}' non è disponibile o è stato "
                "ritirato. Seleziona un modello attuale, per esempio "
                "gemini-3.5-flash."
            )
        if response.status_code == 400 and web_search:
            raise RuntimeError(
                "Google Search Grounding non è disponibile per questo progetto "
                "o piano Gemini. Disattiva la ricerca Gemini oppure configura "
                "la fatturazione in Google AI Studio."
            )
        if response.status_code in GEMINI_RETRYABLE_STATUSES:
            fallback_detail = (
                " e provato il modello alternativo gratuito"
                if switched_model
                else ""
            )
            raise RuntimeError(
                "Gemini è temporaneamente sovraccarico o non disponibile. "
                f"Ho già eseguito i tentativi automatici{fallback_detail}. "
                "Il controllo locale "
                "continua; riprova tra qualche minuto."
            )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini non ha restituito una risposta utilizzabile.")
        parts = candidates[0].get("content", {}).get("parts", [])
        answer = "".join(str(part.get("text", "")) for part in parts).strip()
        if not answer:
            raise RuntimeError("Gemini ha restituito una risposta vuota.")
        grounding = candidates[0].get("groundingMetadata") or {}
        links = []
        for chunk in grounding.get("groundingChunks", []):
            web = chunk.get("web") or {}
            if web.get("uri") and web.get("title"):
                links.append(f"- [{web['title']}]({web['uri']})")
        if links:
            answer += "\n\nFonti:\n" + "\n".join(dict.fromkeys(links))
        return answer

    async def _gemini_request(
        self,
        payload: dict[str, Any],
        allow_fallback: bool,
        preferred_model: str,
    ) -> tuple[httpx.Response, str, bool]:
        models = [preferred_model]
        alternate_model = (
            self.model
            if preferred_model == GEMINI_FALLBACK_MODEL
            else GEMINI_FALLBACK_MODEL
        )
        if allow_fallback and alternate_model not in models:
            models.append(alternate_model)

        last_response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=45) as client:
            for model_index, model in enumerate(models):
                attempts = 2 if model_index == 0 else 1
                for attempt in range(attempts):
                    response = await client.post(
                        f"{self.base_url}/models/{model}:generateContent",
                        headers={
                            "x-goog-api-key": self.api_key,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    last_response = response
                    if response.status_code not in GEMINI_RETRYABLE_STATUSES:
                        return response, model, model_index > 0
                    if attempt < attempts - 1:
                        delay = float(2**attempt)
                        logger.warning(
                            "Gemini %s ha risposto HTTP %s; nuovo tentativo tra %.0fs",
                            model,
                            response.status_code,
                            delay,
                        )
                        await asyncio.sleep(delay)
                if model_index < len(models) - 1:
                    logger.warning(
                        "Gemini %s non disponibile; provo il fallback gratuito %s",
                        model,
                        models[model_index + 1],
                    )

        if last_response is None:
            raise RuntimeError("Nessuna richiesta Gemini è stata eseguita.")
        return last_response, models[-1], len(models) > 1
