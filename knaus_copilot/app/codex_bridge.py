from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .conversational_simulator import run_conversational_simulation
from .learning import ContextLearner
from .memory import MemoryStore
from .permissions import PermissionPolicy


logger = logging.getLogger("mistermif-ai.codex-bridge")

PROTECTED_CHANGE_TERMS = (
    "parametr",
    "firmware",
    "bms",
    "tensione di carica",
    "corrente di carica",
    "ventilazione inverter",
    "riavvia home assistant",
    "spegni home assistant",
    "spegni raspberry",
    "fuori dal workspace",
)


class CollaborationRequest(BaseModel):
    mode: str = Field(pattern="^(discuss|simulate|proposal|self_check)$")
    message: str = Field(min_length=1, max_length=8000)
    sender: str = Field(default="codex", min_length=1, max_length=80)
    request_id: str | None = Field(default=None, max_length=120)


@dataclass
class CollaborationService:
    memory: MemoryStore
    policy: PermissionPolicy
    learner: ContextLearner
    states_provider: Callable[[], Awaitable[list[dict[str, Any]]]]
    health_provider: Callable[[], Awaitable[dict[str, Any]]]
    autonomy_provider: Callable[[], bool]
    animals_provider: Callable[[], bool]
    lab_mode_provider: Callable[[], str]

    async def status(self) -> dict[str, Any]:
        states = await self.states_provider()
        public_states = [
            item for item in states if not bool(item.get("sensitive", False))
        ]
        learning = self.learner.summary()
        return {
            "service": "mistermif-ai-codex-bridge",
            "paired": True,
            "home_assistant": await self.health_provider(),
            "autonomy_enabled": self.autonomy_provider(),
            "animals_on_board": self.animals_provider(),
            "lab_mode": self.lab_mode_provider(),
            "permissions": self.policy.public_summary(),
            "learning": {
                "site_key": learning.site_key,
                "samples": learning.samples,
                "confidence": learning.confidence,
            },
            "visible_states": public_states,
            "inventory": {
                "readable": len(states),
                "shared_with_bridge": len(public_states),
                "sensitive_omitted": len(states) - len(public_states),
            },
            "sensitive_states_omitted": len(states) - len(public_states),
            "bridge_policy": {
                "real_actions": False,
                "configuration_changes": False,
                "simulations_only": True,
                "audit_local": True,
            },
        }

    async def collaborate(
        self, payload: CollaborationRequest
    ) -> dict[str, Any]:
        message = payload.message.strip()
        self.memory.add_message(
            "codex-bridge", "user", f"[{payload.mode}] {message}"
        )

        if payload.mode == "self_check":
            simulation = run_conversational_simulation(
                "Fai un self-check completo di tutte le simulazioni energetiche",
                animals_default=self.animals_provider(),
            )
            consensus = self._simulation_consensus(simulation)
            answer = simulation["answer"] if simulation else "Self-check non disponibile."
        elif payload.mode == "simulate":
            prompt = message
            if "simul" not in prompt.casefold() and "test" not in prompt.casefold():
                prompt = f"Simula {prompt}"
            simulation = run_conversational_simulation(
                prompt,
                animals_default=self.animals_provider(),
            )
            consensus = self._simulation_consensus(simulation)
            answer = (
                simulation["answer"]
                if simulation
                else "La richiesta non contiene dati sufficienti per la simulazione."
            )
        elif payload.mode == "proposal":
            simulation = None
            consensus = self._proposal_consensus(message)
            answer = self._proposal_answer(consensus)
        else:
            simulation = None
            consensus = {
                "status": "information_shared",
                "agreed": True,
                "requires_user_authorization": False,
                "reason": (
                    "Condivido il contesto locale filtrato; nessuna azione reale "
                    "è stata richiesta o eseguita."
                ),
            }
            answer = (
                "Sono collegato a Codex in modalità consultiva. Posso condividere "
                "stato filtrato, memoria operativa, vincoli e risultati del "
                "simulatore. Per una verifica usa simulate o self_check; per una "
                "modifica usa proposal."
            )

        response = {
            "request_id": payload.request_id,
            "sender": "mistermif-ai",
            "answer": answer,
            "consensus": consensus,
            "simulation": simulation,
            "real_actions_executed": [],
            "safety": {
                "bridge_can_execute": False,
                "autonomy_switch_bypassed": False,
                "critical_changes_require_user_authorization": True,
            },
        }
        self.memory.add_message(
            "codex-bridge",
            "assistant",
            json.dumps(
                {
                    "request_id": payload.request_id,
                    "consensus": consensus,
                    "real_actions_executed": [],
                },
                ensure_ascii=False,
            ),
        )
        return response

    @staticmethod
    def _simulation_consensus(
        simulation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not simulation:
            return {
                "status": "needs_revision",
                "agreed": False,
                "requires_user_authorization": False,
                "reason": "Simulazione non riconosciuta.",
            }
        if simulation.get("kind") == "clarification":
            return {
                "status": "needs_more_data",
                "agreed": False,
                "requires_user_authorization": False,
                "reason": "Mancano i dati minimi per un risultato verificabile.",
            }
        passed = bool(
            simulation.get("passed")
            if simulation.get("kind") == "full"
            else simulation.get("assessment", {}).get("passed")
        )
        return {
            "status": "agreed_in_simulation" if passed else "needs_revision",
            "agreed": passed,
            "requires_user_authorization": False,
            "reason": (
                "Codex e Mistermif AI possono usare questo risultato nel gemello "
                "digitale; non equivale a un comando reale."
                if passed
                else "L'autoverifica ha rilevato una condizione da correggere."
            ),
        }

    def _proposal_consensus(self, message: str) -> dict[str, Any]:
        normalized = message.casefold()
        protected = [term for term in PROTECTED_CHANGE_TERMS if term in normalized]
        action_words = (
            "spegni",
            "accendi",
            "cambia",
            "modifica",
            "crea",
            "installa",
            "elimina",
            "riavvia",
        )
        requests_action = any(word in normalized for word in action_words)
        if protected:
            return {
                "status": "requires_user_authorization",
                "agreed": False,
                "requires_user_authorization": True,
                "reason": "La proposta tocca una categoria protetta.",
                "matched_protections": protected,
            }
        if requests_action:
            return {
                "status": "agreement_for_draft_only",
                "agreed": True,
                "requires_user_authorization": True,
                "reason": (
                    "La proposta può essere preparata e simulata, ma il ponte non "
                    "esegue modifiche o comandi reali."
                ),
            }
        return {
            "status": "agreed_for_analysis",
            "agreed": True,
            "requires_user_authorization": False,
            "reason": "La proposta è analitica e resta nel laboratorio locale.",
        }

    @staticmethod
    def _proposal_answer(consensus: dict[str, Any]) -> str:
        status = consensus["status"]
        if status == "requires_user_authorization":
            return (
                "Non approvo l'esecuzione automatica: la proposta riguarda una "
                "categoria protetta e deve essere spiegata e autorizzata dall'utente."
            )
        if status == "agreement_for_draft_only":
            return (
                "Siamo d'accordo nel preparare una bozza e collaudarla nel gemello "
                "digitale. Nessuna modifica reale verrà applicata dal ponte."
            )
        return "Siamo d'accordo nel proseguire con l'analisi nel laboratorio locale."


def create_bridge_app(
    token: str,
    service: CollaborationService,
) -> FastAPI:
    bridge = FastAPI(
        title="mistermif AI Codex Bridge",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    async def authorize(
        authorization: str | None = Header(default=None),
    ) -> None:
        expected = f"Bearer {token}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Token ponte non valido")

    @bridge.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "mistermif-ai-codex-bridge",
            "authentication": "bearer",
        }

    @bridge.get("/v1/status", dependencies=[Depends(authorize)])
    async def status() -> dict[str, Any]:
        return await service.status()

    @bridge.post("/v1/collaborate", dependencies=[Depends(authorize)])
    async def collaborate(payload: CollaborationRequest) -> dict[str, Any]:
        return await service.collaborate(payload)

    return bridge
