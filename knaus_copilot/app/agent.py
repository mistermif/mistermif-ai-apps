from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .memory import MemoryStore
from .permissions import PermissionPolicy


SYSTEM_INSTRUCTIONS = """
Sei mistermif AI, assistente personale della caravan e dei suoi utenti.
Rispondi in italiano, in modo concreto e trasparente.

La versione corrente è esclusivamente osservativa:
- puoi analizzare sensori, energia, meteo, GPS e memoria;
- puoi suggerire azioni e spiegare i motivi;
- non puoi dichiarare di avere eseguito comandi;
- non puoi cambiare parametri di batteria o ventilazione;
- non puoi modificare YAML, firmware, automazioni o configurazioni;
- se i dati sono mancanti o incoerenti, dichiaralo.

Per le condizioni elettriche o meteo urgenti, evidenzia prima il rischio e poi
la raccomandazione. Non confondere il SOC del BMS con quello stimato
dall'inverter. Le decisioni rapide di sicurezza restano alle automazioni locali.
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
