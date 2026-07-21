from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .memory import MemoryStore


PROFILE_KEY = "fridge_optimizer_profile"
SITE_KEY = "fridge:adaptive"
OFFLINE = {"", "unknown", "unavailable", "none", "nan"}


def _text(item: dict[str, Any]) -> str:
    return f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()


def _temperature(item: dict[str, Any]) -> bool:
    return str(item.get("unit", "")).casefold() in {"°c", "c", "°f", "f"} or any(
        word in _text(item) for word in ("temperatur", "temperature", "temp_")
    )


def _value(item: dict[str, Any] | None) -> float | None:
    if not item or str(item.get("state", "")).casefold() in OFFLINE:
        return None
    try:
        return float(item["state"])
    except (TypeError, ValueError):
        return None


class FridgeOptimizer:
    """Local, bounded refrigerator ventilation controller."""

    def __init__(self, memory: MemoryStore, ha, policy, notification_service: str):
        self.memory = memory
        self.ha = ha
        self.policy = policy
        self.notification_service = notification_service
        self.profile = memory.get_json_setting(PROFILE_KEY) or {
            "status": "searching",
            "model": "",
            "entities": {},
            "authorized": False,
        }
        self._sync_permission()

    def _save(self) -> None:
        self.memory.set_json_setting(PROFILE_KEY, self.profile)
        self._sync_permission()

    def _sync_permission(self) -> None:
        entities = self.profile.get("entities", {})
        allowed = {str(entities.get("fan", ""))} if self.profile.get("authorized") else set()
        self.policy.authorize_fridge_control(allowed)

    @staticmethod
    def discover(states: list[dict[str, Any]]) -> dict[str, Any]:
        mapping: dict[str, str] = {}
        fridge = [item for item in states if any(x in _text(item) for x in ("frigo", "fridge", "frigorif", "refriger"))]
        temperatures = [item for item in states if _temperature(item)]

        def first(items, words):
            for item in items:
                if any(word in _text(item) for word in words):
                    return str(item["entity_id"])
            return ""

        mapping["radiator"] = first(
            fridge,
            ("controllo ventole", "radiator", "radiatore", "superior", "upper", "evapor"),
        )
        mapping["internal"] = first(
            [item for item in fridge if _temperature(item) and str(item["entity_id"]) != mapping["radiator"]],
            ("intern", "cella", "vano frigo", "fridge temperature", "temperatura frigo"),
        )
        mapping["external"] = first(
            temperatures,
            ("estern", "external", "outdoor", "fuori"),
        )
        controls = [
            item for item in fridge
            if str(item.get("entity_id", "")).startswith(("fan.", "number.", "input_number."))
            and any(x in _text(item) for x in ("pwm", "percent", "veloc", "fan", "ventol"))
        ]
        mapping["fan"] = str(controls[0]["entity_id"]) if controls else ""
        return {key: value for key, value in mapping.items() if value}

    async def inspect(self, states: list[dict[str, Any]]) -> dict[str, Any]:
        discovered = self.discover(states)
        if discovered and not self.profile.get("authorized"):
            current = dict(self.profile.get("entities", {}))
            current.update({key: value for key, value in discovered.items() if not current.get(key)})
            self.profile["entities"] = current
            self.profile["status"] = "awaiting_details"
            signature = "|".join(sorted(current.values()))
            if signature and signature != self.profile.get("notified_signature"):
                self.profile["notified_signature"] = signature
                try:
                    await self.ha.send_notification(
                        self.notification_service,
                        "Mistermif AI · Frigorifero rilevato",
                        "Ho trovato sensori o ventole riconducibili al frigorifero. Apri la chat: ti chiederò modello, associazioni mancanti e autorizzazione prima di comandare qualsiasi cosa.",
                    )
                except Exception:
                    pass
            self._save()
        return self.public_status()

    def handle_message(self, message: str) -> str | None:
        lowered = message.casefold()
        if not any(word in lowered for word in ("frigo", "frigorif", "fridge", "ventol")):
            return None
        if self.profile.get("authorized") and any(
            phrase in lowered
            for phrase in ("revoco", "togli autorizzazione", "disattiva gestione")
        ):
            self.profile["authorized"] = False
            self.profile["status"] = "awaiting_details"
            self._save()
            return "Autorizzazione alle ventole frigorifero revocata. Il monitoraggio resta in sola osservazione."
        entity_ids = re.findall(r"\b(?:sensor|fan|number|input_number)\.[a-z0-9_]+\b", lowered)
        wants_authorize = any(word in lowered for word in ("autorizzo", "ti autorizzo", "prendi il controllo"))
        if self.profile.get("authorized") and not (entity_ids and wants_authorize):
            sample = self.profile.get("last_sample") or {}
            return (
                f'Gestione frigorifero attiva per {self.profile.get("model") or "modello non indicato"}. '
                f'Ultimo campione: radiatore {sample.get("radiator_c", "n/d")} °C, '
                f'interno {sample.get("internal_c", "n/d")} °C, esterno '
                f'{sample.get("external_c", "n/d")} °C. Ultima decisione: '
                f'{self.profile.get("last_action", "solo osservazione")}.'
            )
        labels = {
            "radiator": ("radiatore", "superiore", "evaporatore", "controllo"),
            "external": ("esterna", "esterno", "fuori"),
            "internal": ("interna", "interno", "cella"),
            "fan": ("ventola", "pwm"),
        }
        entities = dict(self.profile.get("entities", {}))
        for entity_id in entity_ids:
            start = lowered.find(entity_id)
            nearby = lowered[max(0, start - 45):start]
            for key, words in labels.items():
                if any(word in nearby for word in words):
                    entities[key] = entity_id
                    break
        self.profile["entities"] = entities
        model_match = re.search(
            r"(?:marca(?: e modello)?|modello|frigorifero (?:è|e')|frigo (?:è|e'))\s*[:\-]?\s*([^,;\n]+)",
            message,
            re.IGNORECASE,
        )
        if model_match:
            model = model_match.group(1).strip()
            model = re.split(r"\b(?:radiatore|sonda|sensore|ventola|autorizzo)\b", model, flags=re.IGNORECASE)[0].strip()
            if model:
                self.profile["model"] = model[:160]
        missing = [key for key in ("radiator", "external", "internal", "fan") if not entities.get(key)]
        if wants_authorize and not missing and self.profile.get("model"):
            self.policy.authorize_fridge_control({entities["fan"]})
            if entities["fan"] not in self.policy.fridge_control_entities:
                self.profile["authorized"] = False
                self.profile["status"] = "awaiting_details"
                self._save()
                return (
                    "Non autorizzo quel comando: l'entity ID della ventola deve essere "
                    "fan.*, number.* o input_number.*, deve identificare chiaramente il "
                    "frigorifero e non può appartenere alla ventilazione inverter."
                )
            self.profile.update(
                {
                    "authorized": True,
                    "status": "monitoring",
                    "authorized_at": datetime.now(timezone.utc).isoformat(),
                    "base_threshold_c": 40.0,
                    "target_internal_c": 6.0,
                }
            )
            self._save()
            return (
                "Autorizzazione registrata. Monitoro subito il frigorifero e posso comandare esclusivamente "
                f'{entities["fan"]}. Regola iniziale: 100% a 40 °C sul radiatore superiore; '
                "sotto tale soglia osservo senza sostituire i controlli locali. L'apprendimento resta locale."
            )
        self._save()
        details = []
        if not self.profile.get("model"):
            details.append("marca e modello del frigorifero")
        if missing:
            names = {"radiator": "sonda radiatore superiore", "external": "sonda esterna", "internal": "sonda interna", "fan": "comando PWM"}
            details.extend(names[key] for key in missing)
        if details:
            return (
                "Per attivare la gestione frigorifero mi mancano: " + ", ".join(details) + ". "
                "Puoi incollare gli entity_id in una frase, poi scrivere “autorizzo la gestione delle ventole frigo”."
            )
        return (
            f'Ho identificato {self.profile.get("model") or "il frigorifero"} e le quattro entità necessarie. '
            "Se le associazioni sono corrette, scrivi “autorizzo la gestione delle ventole frigo”."
        )

    async def monitor_once(self) -> dict[str, Any]:
        states = await self.ha.fridge_states()
        await self.inspect(states)
        if not self.profile.get("authorized"):
            return self.public_status()
        by_id = {str(item["entity_id"]): item for item in states}
        entities = self.profile["entities"]
        readings = {key: _value(by_id.get(entity_id)) for key, entity_id in entities.items()}
        sample = {
            "radiator_c": readings.get("radiator"),
            "external_c": readings.get("external"),
            "internal_c": readings.get("internal"),
            "fan_percent": readings.get("fan"),
        }
        if all(sample[key] is not None for key in ("radiator_c", "external_c", "internal_c")):
            self.memory.add_learning_observation(SITE_KEY, sample)
        radiator = sample["radiator_c"]
        action = "observe"
        if radiator is not None and radiator >= 40.0 and self.policy.runtime_enabled:
            await self.ha.set_fridge_fan(entities["fan"], 100.0)
            action = "fan_100"
        elif radiator is not None and radiator >= 40.0:
            action = "fan_100_blocked_by_autonomy"
        self.profile["last_sample"] = sample
        self.profile["last_action"] = action
        self.profile["last_check"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return self.public_status()

    def public_status(self) -> dict[str, Any]:
        entities = dict(self.profile.get("entities", {}))
        return {
            "status": self.profile.get("status", "searching"),
            "model": self.profile.get("model", ""),
            "entities": entities,
            "missing": [key for key in ("radiator", "external", "internal", "fan") if not entities.get(key)],
            "authorized": bool(self.profile.get("authorized")),
            "base_rule": "100% a 40 °C sul radiatore superiore",
            "last_sample": self.profile.get("last_sample"),
            "last_action": self.profile.get("last_action", "none"),
            "local_learning": True,
        }
