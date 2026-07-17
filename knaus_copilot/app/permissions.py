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


@dataclass(frozen=True)
class PermissionPolicy:
    autonomy_mode: str = "observe"

    def can_read(self, entity_id: str) -> bool:
        return entity_id.startswith(READ_PREFIXES)

    def is_sensitive(self, entity_id: str) -> bool:
        lowered = entity_id.lower()
        return any(fragment in lowered for fragment in SENSITIVE_ENTITY_FRAGMENTS)

    def can_execute(self, tool_name: str) -> bool:
        # Versione 0.1: nessun comando operativo, indipendentemente dalla modalità.
        return False

    def public_summary(self) -> dict:
        return {
            "mode": self.autonomy_mode,
            "read_only": True,
            "allowed_actions": [],
            "blocked_categories": [
                "parametri batteria",
                "parametri ventilazione inverter",
                "firmware ESPHome",
                "modifica YAML",
                "riavvio o spegnimento",
            ],
        }

