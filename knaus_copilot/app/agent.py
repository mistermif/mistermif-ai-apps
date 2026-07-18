from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .memory import MemoryStore
from .permissions import PermissionPolicy


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
    ):
        self.model = model
        self.memory = memory
        self.policy = policy
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    async def chat(
        self,
        user_id: str,
        message: str,
        ha_states: list[dict[str, Any]],
    ) -> str:
        self.memory.add_message(user_id, "user", message)
        if self.client is None:
            answer = (
                "La chiave OpenAI API non è ancora configurata. "
                "La memoria locale e la lettura di Home Assistant sono operative."
            )
            self.memory.add_message(user_id, "assistant", answer)
            return answer

        history = self.memory.recent_messages(user_id, limit=16)
        memories = self.memory.list_memories(user_id, limit=20)
        context = {
            "home_assistant": ha_states,
            "memories": memories,
            "permissions": self.policy.public_summary(),
        }
        conversation = [
            {"role": item["role"], "content": item["content"]}
            for item in history[:-1]
        ]
        conversation.append(
            {
                "role": "user",
                "content": (
                    f"CONTESTO ATTUALE:\n{json.dumps(context, ensure_ascii=False)}"
                    f"\n\nRICHIESTA:\n{message}"
                ),
            }
        )
        response = await self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=conversation,
        )
        answer = response.output_text.strip()
        self.memory.add_message(user_id, "assistant", answer)
        return answer
