from __future__ import annotations

import json
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


SYSTEM_INSTRUCTIONS = """
Sei mistermif AI, assistente personale della caravan e dei suoi utenti.
Rispondi in italiano, in modo concreto e trasparente.

Il tuo perimetro operativo è definito dalla politica ricevuta nel contesto:
- puoi analizzare sensori, energia, meteo, GPS e memoria;
- puoi suggerire azioni e spiegare i motivi;
- puoi dichiarare eseguita un'azione soltanto quando ricevi il risultato reale;
- non puoi cambiare parametri di batteria o ventilazione;
- non puoi modificare YAML, firmware, automazioni o configurazioni;
- se i dati sono mancanti o incoerenti, dichiaralo.

Per le condizioni elettriche o meteo urgenti, evidenzia prima il rischio e poi
la raccomandazione. Non confondere il SOC del BMS con quello stimato
dall'inverter. Le decisioni rapide di sicurezza restano alle automazioni locali.

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

    async def chat(
        self,
        user_id: str,
        message: str,
        ha_states: list[dict[str, Any]],
        automatic: bool = False,
        web_search: bool = False,
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

        history = self.memory.recent_messages(user_id, limit=16)
        memories = self.memory.list_memories(user_id, limit=20)
        context = {
            "home_assistant": self.privacy.sanitize_states(ha_states),
            "memories": self.privacy.sanitize_memories(memories),
            "permissions": self.policy.public_summary(),
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

    async def _gemini(
        self,
        conversation: list[dict[str, str]],
        web_search: bool,
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
        }
        if web_search:
            payload["tools"] = [{"google_search": {}}]
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code == 401 or response.status_code == 403:
            raise RuntimeError("Chiave Gemini non valida o non autorizzata.")
        if response.status_code == 429:
            raise RuntimeError(
                "Limite Gemini temporaneamente raggiunto; "
                "il controllo locale continua."
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
