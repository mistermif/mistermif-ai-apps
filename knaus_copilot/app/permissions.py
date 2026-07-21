from __future__ import annotations

from dataclasses import dataclass


READ_PREFIXES = (
    "sensor.",
    "binary_sensor.",
    "weather.",
    "device_tracker.caravan",
    "climate.thermal_control",
    "select.2_output_source_priority",
    "input_boolean.energia_",
    "input_number.energia_",
    "input_select.energia_",
)

SENSITIVE_ENTITY_FRAGMENTS = (
    "bulk_charging_voltage",
    "float_charging_voltage",
    "low_dc_cut",
    "comeback_battery",
    "comeback_utility",
    "max_total_charge",
    "utility_charge_current",
    "ventilazione",
    "cooling_",
)


@dataclass
class PermissionPolicy:
    autonomy_mode: str = "observe"
    climate_entity: str = "climate.thermal_control"
    runtime_enabled: bool = False

    def can_read(self, entity_id: str) -> bool:
        return entity_id.startswith(READ_PREFIXES)

    def is_sensitive(self, entity_id: str) -> bool:
        lowered = entity_id.lower()
        return any(fragment in lowered for fragment in SENSITIVE_ENTITY_FRAGMENTS)

    def can_execute(self, tool_name: str) -> bool:
        if tool_name == "send_notification":
            return True
        return self.runtime_enabled and tool_name == "turn_off_climate"

    def can_control_entity(self, entity_id: str) -> bool:
        return self.can_execute("turn_off_climate") and entity_id == self.climate_entity

    def public_summary(self) -> dict:
        return {
            "mode": "limited" if self.runtime_enabled else "observe",
            "read_only": not self.runtime_enabled,
            "allowed_actions": (
                ["spegnimento climatizzatore", "invio notifiche"]
                if self.can_execute("turn_off_climate")
                else ["invio notifiche"]
            ),
            "confirmation_required": False,
            "blocked_categories": [
                "parametri batteria",
                "parametri ventilazione inverter",
                "firmware ESPHome",
                "modifiche YAML fuori dal workspace dedicato",
                "riavvio o spegnimento di sistema",
            ],
            "external_changes": {
                "always_require_confirmation": True,
                "required_explanation": [
                    "motivo",
                    "file o configurazione coinvolta",
                    "rischio",
                    "backup e ripristino",
                ],
            },
        }
