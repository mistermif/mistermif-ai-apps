from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .memory import MemoryStore


PROFILE_KEY = "fridge_optimizer_profile"
SITE_KEY = "fridge:adaptive"
OFFLINE = {"", "unknown", "unavailable", "none", "nan"}
PARAMETER_WORDS = {
    "day_start_pwm": ("giorno pwm start", "day pwm start"),
    "day_start_temp": ("giorno temp start", "day temp start"),
    "day_full_temp": ("giorno temp pwm 100", "day temp pwm 100"),
    "day_hysteresis": ("giorno isteresi", "day hysteresis"),
    "night_start_pwm": ("notte pwm start", "night pwm start"),
    "night_start_temp": ("notte temp start", "night temp start"),
    "night_full_temp": ("notte temp pwm 100", "night temp pwm 100"),
    "night_hysteresis": ("notte isteresi", "night hysteresis"),
}


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


def _numeric_value(item: dict[str, Any] | None) -> float | None:
    if not item or str(item.get("state", "")).casefold() in OFFLINE:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(item.get("state", "")))
    return float(match.group(0).replace(",", ".")) if match else None


def _fan_percent(item: dict[str, Any] | None) -> float | None:
    if not item:
        return None
    percentage = (item.get("attributes") or {}).get("percentage")
    if percentage is not None:
        try:
            return float(percentage)
        except (TypeError, ValueError):
            return None
    return _numeric_value(item)


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
        legacy_fan = str(self.profile.get("entities", {}).get("fan", "")).casefold()
        if self.profile.get("authorized") and "manual" in legacy_fan:
            self.profile["authorized"] = False
            self.profile["status"] = "searching"
            self.profile["migration_note"] = (
                "Autorizzazione PWM manuale revocata: è richiesta la nuova "
                "rilevazione del controller locale."
            )
            self.memory.set_json_setting(PROFILE_KEY, self.profile)
        self._sync_permission()

    def _save(self) -> None:
        self.memory.set_json_setting(PROFILE_KEY, self.profile)
        self._sync_permission()

    def _sync_permission(self) -> None:
        entities = self.profile.get("entities", {})
        parameters = entities.get("parameters", {})
        allowed = set()
        if self.profile.get("authorized"):
            allowed = {
                str(entities.get("fan", "")),
                *(str(value) for value in parameters.values()),
            }
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
        direct_controls = [
            item for item in fridge
            if str(item.get("entity_id", "")).startswith(("fan.", "number.", "input_number."))
            and any(x in _text(item) for x in ("pwm", "percent", "veloc", "fan", "ventol"))
            and not any(x in _text(item) for x in ("giorno", "notte", "day", "night", "manual"))
        ]
        mapping["fan"] = str(direct_controls[0]["entity_id"]) if direct_controls else ""
        parameters = {}
        for key, words in PARAMETER_WORDS.items():
            entity_id = first(fridge, words)
            if entity_id:
                parameters[key] = entity_id
        if parameters:
            mapping["parameters"] = parameters
            mapping["mode"] = "local_controller"
        elif mapping["fan"]:
            mapping["mode"] = "direct_pwm"
        return {key: value for key, value in mapping.items() if value}

    async def inspect(self, states: list[dict[str, Any]]) -> dict[str, Any]:
        discovered = self.discover(states)
        if discovered and not self.profile.get("authorized"):
            current = dict(self.profile.get("entities", {}))
            current_parameters = dict(current.get("parameters", {}))
            current_parameters.update(discovered.get("parameters", {}))
            current.update({key: value for key, value in discovered.items() if not current.get(key)})
            if current_parameters:
                current["parameters"] = current_parameters
            self.profile["entities"] = current
            self.profile["status"] = "awaiting_details"
            signature_values = [str(value) for key, value in current.items() if key != "parameters"]
            signature_values.extend(str(value) for value in current_parameters.values())
            signature = "|".join(sorted(signature_values))
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
        entity_ids = re.findall(r"\b(?:sensor|fan|number|input_number|select)\.[a-z0-9_]+\b", lowered)
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
        mode = entities.get("mode") or ("direct_pwm" if entities.get("fan") else "")
        parameters = entities.get("parameters", {})
        missing = [key for key in ("radiator", "external", "internal") if not entities.get(key)]
        if mode == "local_controller":
            if any(not parameters.get(key) for key in PARAMETER_WORDS):
                missing.append("controller_parameters")
        elif not entities.get("fan"):
            missing.append("fan")
        if wants_authorize and not missing and self.profile.get("model"):
            requested_controls = (
                set(parameters.values())
                if mode == "local_controller"
                else {entities["fan"]}
            )
            self.policy.authorize_fridge_control(requested_controls)
            if requested_controls != self.policy.fridge_control_entities:
                self.profile["authorized"] = False
                self.profile["status"] = "awaiting_details"
                self._save()
                return (
                    "Non autorizzo quei comandi: gli entity ID devono essere fan.*, "
                    "number.*, input_number.* o select.*, identificare chiaramente il "
                    "frigorifero e non appartenere alla ventilazione inverter."
                )
            self.profile.update(
                {
                    "authorized": True,
                    "status": "monitoring",
                    "control_mode": mode,
                    "authorized_at": datetime.now(timezone.utc).isoformat(),
                    "base_threshold_c": 40.0,
                    "target_internal_c": 6.0,
                }
            )
            self._save()
            control_description = (
                "ottimizzare i parametri giorno/notte del controller ESPHome"
                if mode == "local_controller"
                else f'comandare direttamente {entities["fan"]}'
            )
            return (
                "Autorizzazione registrata. Posso " + control_description + ". "
                "Obiettivo iniziale: massima resa, con 100% a 40 °C sul radiatore "
                "superiore. L'apprendimento e le correzioni restano locali e vincolati."
            )
        self._save()
        details = []
        if not self.profile.get("model"):
            details.append("marca e modello del frigorifero")
        if missing:
            names = {"radiator": "sonda radiatore superiore", "external": "sonda esterna", "internal": "sonda interna", "fan": "comando PWM", "controller_parameters": "parametri completi del controller giorno/notte"}
            details.extend(names[key] for key in missing)
        if details:
            return (
                "Per attivare la gestione frigorifero mi mancano: " + ", ".join(details) + ". "
                "Puoi incollare gli entity_id in una frase, poi scrivere “autorizzo la gestione delle ventole frigo”."
            )
        return (
            f'Ho identificato {self.profile.get("model") or "il frigorifero"} e le entità necessarie. '
            "Se le associazioni sono corrette, scrivi “autorizzo la gestione delle ventole frigo”."
        )

    def _learned_bias(self) -> tuple[int, int, float]:
        observations = self.memory.recent_learning_observations(SITE_KEY, limit=4000)
        if len(observations) < 60:
            return 0, 0, 0.0
        try:
            first = datetime.fromisoformat(observations[0]["observed_at"].replace("Z", "+00:00"))
            last = datetime.fromisoformat(observations[-1]["observed_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            return 0, 0, 0.0
        hours = max(0.0, (last - first).total_seconds() / 3600.0)
        confidence = min(1.0, hours / 48.0)
        if hours < 36.0:
            return 0, 0, confidence
        values = sorted(
            float(item["payload"]["internal_c"])
            for item in observations
            if item.get("payload", {}).get("internal_c") is not None
        )
        if not values:
            return 0, 0, confidence
        p90 = values[min(len(values) - 1, int(len(values) * 0.9))]
        if p90 >= 8.0:
            return -2, 20, confidence
        if p90 >= 7.0:
            return -1, 10, confidence
        return 0, 0, confidence

    def _controller_targets(self, internal_c: float, external_c: float) -> dict[str, float]:
        """Return bounded performance-first values supported by the ESPHome selects."""
        if internal_c >= 8.0:
            day_start, day_full, day_pwm = 30, 38, 70
            night_start, night_full, night_pwm = 32, 39, 60
        elif internal_c >= 6.0:
            day_start, day_full, day_pwm = 32, 39, 60
            night_start, night_full, night_pwm = 34, 40, 50
        else:
            day_start, day_full, day_pwm = 33, 40, 50
            night_start, night_full, night_pwm = 35, 40, 40
        if external_c >= 32.0:
            day_start = max(28, day_start - 1)
            night_start = max(30, night_start - 1)
        temp_bias, pwm_bias, confidence = self._learned_bias()
        day_start = max(25, day_start + temp_bias)
        night_start = max(25, night_start + temp_bias)
        day_full = max(day_start + 3, min(40, day_full + temp_bias))
        night_full = max(night_start + 3, min(40, night_full + temp_bias))
        day_pwm = min(90, day_pwm + pwm_bias)
        night_pwm = min(90, night_pwm + pwm_bias)
        self.profile["learning_confidence"] = round(confidence, 3)
        return {
            "day_start_pwm": day_pwm,
            "day_start_temp": day_start,
            "day_full_temp": day_full,
            "day_hysteresis": 2,
            "night_start_pwm": night_pwm,
            "night_start_temp": night_start,
            "night_full_temp": night_full,
            "night_hysteresis": 2,
        }

    def _direct_target(self, radiator_c: float, internal_c: float) -> float:
        if radiator_c >= 40.0 or internal_c >= 9.0:
            return 100.0
        if radiator_c >= 35.0:
            return 70.0 + (radiator_c - 35.0) * 6.0
        if radiator_c >= 30.0:
            return 40.0 + (radiator_c - 30.0) * 6.0
        if radiator_c <= 28.0:
            return 0.0
        return float(self.profile.get("last_commanded_pwm", 0.0))

    def _tuning_due(self) -> bool:
        last = self.profile.get("last_tuning_at")
        if not last:
            return True
        try:
            timestamp = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        except ValueError:
            return True
        return datetime.now(timezone.utc) - timestamp >= timedelta(hours=6)

    async def _tune_local_controller(
        self,
        by_id: dict[str, dict[str, Any]],
        internal_c: float,
        external_c: float,
    ) -> list[dict[str, Any]]:
        parameters = self.profile["entities"].get("parameters", {})
        targets = self._controller_targets(internal_c, external_c)
        changes = []
        for key, target in targets.items():
            entity_id = parameters.get(key)
            if not entity_id:
                continue
            current = _numeric_value(by_id.get(entity_id))
            if current is not None and abs(current - target) < 0.1:
                continue
            changes.append(await self.ha.set_fridge_parameter(entity_id, target))
        self.profile["last_tuning_at"] = datetime.now(timezone.utc).isoformat()
        self.profile["controller_targets"] = targets
        return changes

    async def monitor_once(self) -> dict[str, Any]:
        states = await self.ha.fridge_states()
        await self.inspect(states)
        if not self.profile.get("authorized"):
            return self.public_status()
        by_id = {str(item["entity_id"]): item for item in states}
        entities = self.profile["entities"]
        readings = {
            key: _value(by_id.get(entity_id))
            for key, entity_id in entities.items()
            if key in {"radiator", "external", "internal"}
        }
        sample = {
            "radiator_c": readings.get("radiator"),
            "external_c": readings.get("external"),
            "internal_c": readings.get("internal"),
            "fan_percent": _fan_percent(by_id.get(str(entities.get("fan", "")))),
        }
        if all(sample[key] is not None for key in ("radiator_c", "external_c", "internal_c")):
            self.memory.add_learning_observation(SITE_KEY, sample)
        radiator = sample["radiator_c"]
        internal = sample["internal_c"]
        external = sample["external_c"]
        action = "observe"
        mode = self.profile.get("control_mode") or entities.get("mode", "direct_pwm")
        if None not in (radiator, internal, external):
            if not self.policy.runtime_enabled:
                action = "control_blocked_by_autonomy"
            elif mode == "local_controller" and self._tuning_due():
                changes = await self._tune_local_controller(by_id, internal, external)
                action = f"controller_tuned:{len(changes)}"
            elif mode == "local_controller":
                action = "controller_monitoring"
            elif entities.get("fan"):
                target = round(self._direct_target(radiator, internal) / 5.0) * 5.0
                previous = self.profile.get("last_commanded_pwm")
                if previous is None or abs(float(previous) - target) >= 5.0:
                    await self.ha.set_fridge_fan(entities["fan"], target)
                    self.profile["last_commanded_pwm"] = target
                    action = f"direct_pwm:{round(target)}"
                else:
                    action = f"direct_pwm_stable:{round(target)}"
        self.profile["last_sample"] = sample
        self.profile["last_action"] = action
        self.profile["last_check"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return self.public_status()

    def public_status(self) -> dict[str, Any]:
        entities = dict(self.profile.get("entities", {}))
        mode = self.profile.get("control_mode") or entities.get("mode", "not_detected")
        missing = [key for key in ("radiator", "external", "internal") if not entities.get(key)]
        if mode == "local_controller":
            parameters = entities.get("parameters", {})
            if any(not parameters.get(key) for key in PARAMETER_WORDS):
                missing.append("controller_parameters")
        elif not entities.get("fan"):
            missing.append("fan")
        return {
            "status": self.profile.get("status", "searching"),
            "model": self.profile.get("model", ""),
            "entities": entities,
            "missing": missing,
            "authorized": bool(self.profile.get("authorized")),
            "base_rule": "100% a 40 °C sul radiatore superiore",
            "last_sample": self.profile.get("last_sample"),
            "last_action": self.profile.get("last_action", "none"),
            "control_mode": mode,
            "controller_targets": self.profile.get("controller_targets"),
            "migration_note": self.profile.get("migration_note"),
            "local_learning": True,
            "learning_confidence": self.profile.get("learning_confidence", 0.0),
        }
