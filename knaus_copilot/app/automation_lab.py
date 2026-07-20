from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


LAB_VERSION = "1.0"


@dataclass(frozen=True)
class LabSnapshot:
    battery_soc: float
    battery_current: float
    grid_power: float
    external_power: float
    solar_power: float
    available_amps: int
    climate_on: bool
    external_charge: bool
    hour: int
    sensors_available: bool = True
    animals_on_board: bool = False
    external_socket_parallel: bool = False
    battery_trend_percent_per_hour: float = 0.0


@dataclass(frozen=True)
class LabScenario:
    scenario_id: str
    label: str
    purpose: str
    snapshot: LabSnapshot


SCENARIOS = {
    item.scenario_id: item
    for item in (
        LabScenario(
            "sensori_offline",
            "Sensori offline",
            "Verifica che un dato mancante non provochi comandi o falsi allarmi.",
            LabSnapshot(
                battery_soc=0,
                battery_current=0,
                grid_power=0,
                external_power=0,
                solar_power=0,
                available_amps=6,
                climate_on=True,
                external_charge=False,
                hour=12,
                sensors_available=False,
            ),
        ),
        LabScenario(
            "batteria_critica_senza_sole",
            "Batteria 19%, nessuna ricarica",
            "Simula la protezione del clima senza scaricare la batteria reale.",
            LabSnapshot(
                battery_soc=19,
                battery_current=-42,
                grid_power=0,
                external_power=0,
                solar_power=0,
                available_amps=6,
                climate_on=True,
                external_charge=False,
                hour=18,
                battery_trend_percent_per_hour=-7,
            ),
        ),
        LabScenario(
            "batteria_bassa_in_recupero",
            "Batteria 24%, sole in crescita",
            "Verifica che una ricarica reale eviti uno spegnimento prematuro.",
            LabSnapshot(
                battery_soc=24,
                battery_current=28,
                grid_power=0,
                external_power=0,
                solar_power=520,
                available_amps=6,
                climate_on=True,
                external_charge=False,
                hour=9,
                battery_trend_percent_per_hour=5,
            ),
        ),
        LabScenario(
            "colonnina_6a_quasi_limite",
            "Colonnina 6 A quasi al limite",
            "Simula una salita rapida del carico prima dello sgancio della colonnina.",
            LabSnapshot(
                battery_soc=82,
                battery_current=3,
                grid_power=1325,
                external_power=0,
                solar_power=180,
                available_amps=6,
                climate_on=True,
                external_charge=False,
                hour=12,
            ),
        ),
        LabScenario(
            "colonnina_10a_presa_esterna",
            "10 A con presa esterna",
            "Somma PZEM e presa esterna collegata in parallelo alla colonnina.",
            LabSnapshot(
                battery_soc=76,
                battery_current=1,
                grid_power=720,
                external_power=1420,
                solar_power=120,
                available_amps=10,
                climate_on=True,
                external_charge=False,
                hour=13,
                external_socket_parallel=True,
            ),
        ),
        LabScenario(
            "animali_batteria_bassa",
            "Animali a bordo e batteria bassa",
            "Verifica che il clima resti prioritario e venga richiesta assistenza.",
            LabSnapshot(
                battery_soc=18,
                battery_current=-48,
                grid_power=0,
                external_power=0,
                solar_power=20,
                available_amps=6,
                climate_on=True,
                external_charge=False,
                hour=17,
                animals_on_board=True,
                battery_trend_percent_per_hour=-8,
            ),
        ),
    )
}


def public_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": scenario.scenario_id,
            "label": scenario.label,
            "purpose": scenario.purpose,
            "snapshot": asdict(scenario.snapshot),
        }
        for scenario in SCENARIOS.values()
    ]


def evaluate_snapshot(
    snapshot: LabSnapshot,
    *,
    source: str = "simulation",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    limit_watts = snapshot.available_amps * 230
    observed_grid_watts = snapshot.grid_power
    if snapshot.external_socket_parallel:
        observed_grid_watts += snapshot.external_power
    load_ratio = observed_grid_watts / limit_watts if limit_watts else 0

    result: dict[str, Any] = {
        "lab_version": LAB_VERSION,
        "evaluated_at": now,
        "source": source,
        "conclusive": True,
        "severity": "ok",
        "decision": "monitor",
        "reason": "",
        "allowed_actions": [],
        "protected_recommendations": [],
        "executed_actions": [],
        "metrics": {
            "grid_limit_watts": limit_watts,
            "observed_grid_watts": round(observed_grid_watts, 1),
            "load_ratio": round(load_ratio, 3),
            "battery_soc": snapshot.battery_soc,
            "solar_power": snapshot.solar_power,
        },
        "safety": {
            "real_services_called": False,
            "inverter_parameters_mutated": False,
            "battery_discharged_by_test": False,
        },
    }

    if not snapshot.sensors_available:
        result.update(
            {
                "conclusive": False,
                "severity": "allerta",
                "decision": "wait_for_valid_data",
                "reason": (
                    "I sensori necessari non sono disponibili: nessun comando "
                    "viene dedotto da valori unknown o unavailable."
                ),
            }
        )
        return result

    charging_recovery = (
        snapshot.external_charge
        or snapshot.solar_power >= 250
        or snapshot.battery_current >= 8
        or snapshot.battery_trend_percent_per_hour >= 1
    )

    if snapshot.animals_on_board and snapshot.battery_soc <= 30:
        result.update(
            {
                "severity": "emergenza"
                if snapshot.battery_soc <= 12
                else "urgenza",
                "decision": "protect_climate_and_escalate",
                "reason": (
                    "Con animali a bordo il clima resta prioritario. Occorre "
                    "trovare una fonte di energia e avvisare subito l'equipaggio."
                ),
                "allowed_actions": ["send_notification"],
            }
        )
        return result

    if snapshot.battery_soc <= 20 and not charging_recovery:
        actions = ["send_notification"]
        if snapshot.climate_on:
            actions.insert(0, "turn_off_climate")
        result.update(
            {
                "severity": "emergenza"
                if snapshot.battery_soc <= 10
                else "urgenza",
                "decision": "protect_battery",
                "reason": (
                    "SOC critico, batteria in scarica e nessuna ricarica "
                    "sufficiente rilevata."
                ),
                "allowed_actions": actions,
            }
        )
        return result

    if snapshot.battery_soc <= 30:
        if charging_recovery:
            result.update(
                {
                    "severity": "allerta",
                    "decision": "observe_recovery",
                    "reason": (
                        "Il SOC è basso, ma produzione o corrente batteria "
                        "indicano un recupero reale: si monitora prima di agire."
                    ),
                }
            )
        elif snapshot.hour >= 17 and snapshot.battery_trend_percent_per_hour < -2:
            actions = ["send_notification"]
            if snapshot.climate_on:
                actions.insert(0, "turn_off_climate")
            result.update(
                {
                    "severity": "urgenza",
                    "decision": "protect_before_night",
                    "reason": (
                        "Il SOC cala rapidamente verso sera e non risultano "
                        "fonti di ricarica: intervento anticipato nel margine "
                        "autorizzato."
                    ),
                    "allowed_actions": actions,
                }
            )
        else:
            result.update(
                {
                    "severity": "allerta",
                    "decision": "monitor_low_soc",
                    "reason": "SOC basso ma senza una condizione sufficiente per agire.",
                }
            )

    if load_ratio >= 0.92:
        actions = list(result["allowed_actions"])
        if snapshot.climate_on and "turn_off_climate" not in actions:
            actions.append("turn_off_climate")
        if "send_notification" not in actions:
            actions.append("send_notification")
        result.update(
            {
                "severity": "urgenza",
                "decision": "prevent_shore_trip",
                "reason": (
                    f"Il carico stimato è al {load_ratio * 100:.0f}% del limite "
                    "della colonnina. Il clima può essere alleggerito; il cambio "
                    "SBU resta protetto finché non viene autorizzato e collaudato."
                ),
                "allowed_actions": actions,
                "protected_recommendations": ["request_inverter_sbu"],
            }
        )

    return result


def run_scenario(scenario_id: str) -> dict[str, Any]:
    try:
        scenario = SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError("Scenario di simulazione sconosciuto") from exc
    result = evaluate_snapshot(scenario.snapshot)
    result["scenario"] = {
        "id": scenario.scenario_id,
        "label": scenario.label,
        "purpose": scenario.purpose,
        "snapshot": asdict(scenario.snapshot),
    }
    return result


def snapshot_from_home_assistant(
    states: list[dict[str, Any]],
    mapping: dict[str, str],
    *,
    default_available_amps: int = 6,
    hour: int | None = None,
) -> LabSnapshot:
    by_entity = {
        str(item.get("entity_id")): item
        for item in states
        if item.get("entity_id")
    }
    unavailable_values = {"unknown", "unavailable", "none", ""}
    required = ("battery_soc", "grid_power", "solar_power")

    def raw(key: str) -> Any:
        entity_id = mapping.get(key, "")
        item = by_entity.get(entity_id, {})
        return item.get("state")

    def is_valid(key: str) -> bool:
        value = raw(key)
        return value is not None and str(value).strip().casefold() not in (
            unavailable_values
        )

    def number(key: str, default: float = 0.0) -> float:
        if not is_valid(key):
            return default
        try:
            return float(raw(key))
        except (TypeError, ValueError):
            return default

    def boolean(key: str, default: bool = False) -> bool:
        if not is_valid(key):
            return default
        return str(raw(key)).strip().casefold() in {
            "on",
            "true",
            "yes",
            "1",
            "heat",
            "cool",
            "fan_only",
            "dry",
        }

    required_available = all(mapping.get(key) and is_valid(key) for key in required)
    available_amps = int(round(number("available_amps", default_available_amps)))
    available_amps = min(16, max(3, available_amps))
    return LabSnapshot(
        battery_soc=number("battery_soc"),
        battery_current=number("battery_current"),
        grid_power=number("grid_power"),
        external_power=number("external_power"),
        solar_power=number("solar_power"),
        available_amps=available_amps,
        climate_on=boolean("climate"),
        external_charge=boolean("external_charge"),
        hour=hour if hour is not None else datetime.now().hour,
        sensors_available=required_available,
        animals_on_board=boolean("animals_on_board"),
        external_socket_parallel=boolean("external_socket_parallel"),
        battery_trend_percent_per_hour=number("battery_trend"),
    )


LAB_PACKAGE_YAML = """\
# Generato da mistermif AI - Energy Safety Lab
# Usa esclusivamente helper virtuali. Non chiama servizi reali.
input_select:
  mistermif_ai_lab_scenario:
    name: Mistermif AI - Scenario laboratorio
    options:
      - Sensori offline
      - Batteria critica senza sole
      - Batteria bassa in recupero
      - Colonnina 6 A quasi al limite
      - Colonnina 10 A con presa esterna
      - Animali a bordo e batteria bassa
    initial: Sensori offline
    icon: mdi:test-tube

input_number:
  mistermif_ai_lab_battery_soc:
    name: Mistermif AI Lab - SOC batteria
    min: 0
    max: 100
    step: 1
    initial: 80
    unit_of_measurement: "%"
    icon: mdi:battery
  mistermif_ai_lab_battery_current:
    name: Mistermif AI Lab - Corrente batteria
    min: -150
    max: 150
    step: 1
    initial: 0
    unit_of_measurement: "A"
    icon: mdi:current-dc
  mistermif_ai_lab_grid_power:
    name: Mistermif AI Lab - Potenza PZEM
    min: 0
    max: 4000
    step: 10
    initial: 0
    unit_of_measurement: "W"
    icon: mdi:transmission-tower
  mistermif_ai_lab_external_power:
    name: Mistermif AI Lab - Presa esterna
    min: 0
    max: 4000
    step: 10
    initial: 0
    unit_of_measurement: "W"
    icon: mdi:power-socket-eu
  mistermif_ai_lab_solar_power:
    name: Mistermif AI Lab - Produzione solare
    min: 0
    max: 1500
    step: 10
    initial: 0
    unit_of_measurement: "W"
    icon: mdi:solar-power
  mistermif_ai_lab_available_amps:
    name: Mistermif AI Lab - Ampere colonnina
    min: 3
    max: 16
    step: 1
    initial: 6
    unit_of_measurement: "A"
    icon: mdi:current-ac

input_boolean:
  mistermif_ai_lab_climate_on:
    name: Mistermif AI Lab - Clima acceso
    icon: mdi:air-conditioner
  mistermif_ai_lab_external_parallel:
    name: Mistermif AI Lab - Presa esterna in parallelo
    icon: mdi:power-plug
  mistermif_ai_lab_animals_on_board:
    name: Mistermif AI Lab - Animali a bordo
    icon: mdi:dog

template:
  - sensor:
      - name: Mistermif AI Lab - Limite colonnina
        unique_id: mistermif_ai_lab_grid_limit
        unit_of_measurement: "W"
        state: >-
          {{ states('input_number.mistermif_ai_lab_available_amps') | float(0) * 230 }}
      - name: Mistermif AI Lab - Carico colonnina
        unique_id: mistermif_ai_lab_grid_load
        unit_of_measurement: "W"
        state: >-
          {% set base = states('input_number.mistermif_ai_lab_grid_power') | float(0) %}
          {% set ext = states('input_number.mistermif_ai_lab_external_power') | float(0) %}
          {{ base + (ext if is_state('input_boolean.mistermif_ai_lab_external_parallel', 'on') else 0) }}
      - name: Mistermif AI Lab - Margine colonnina
        unique_id: mistermif_ai_lab_grid_margin
        unit_of_measurement: "W"
        state: >-
          {{ (states('sensor.mistermif_ai_lab_limite_colonnina') | float(0) -
              states('sensor.mistermif_ai_lab_carico_colonnina') | float(0)) | round(0) }}
      - name: Mistermif AI Lab - Esito locale
        unique_id: mistermif_ai_lab_local_result
        state: >-
          {% set soc = states('input_number.mistermif_ai_lab_battery_soc') | float(0) %}
          {% set solar = states('input_number.mistermif_ai_lab_solar_power') | float(0) %}
          {% set load = states('sensor.mistermif_ai_lab_carico_colonnina') | float(0) %}
          {% set limit = states('sensor.mistermif_ai_lab_limite_colonnina') | float(1) %}
          {% if is_state('input_boolean.mistermif_ai_lab_animals_on_board', 'on') and soc <= 30 %}
            proteggi_clima_e_avvisa
          {% elif soc <= 20 and solar < 250 %}
            proteggi_batteria
          {% elif load >= limit * 0.92 %}
            previeni_sgancio_colonnina
          {% elif soc <= 30 and solar >= 250 %}
            osserva_recupero
          {% else %}
            monitora
          {% endif %}

automation:
  - id: mistermif_ai_lab_scenario_trace
    alias: Mistermif AI Lab - Registra cambio scenario
    description: Automazione fissa di prova; genera solo un evento locale.
    mode: restart
    trigger:
      - platform: state
        entity_id: input_select.mistermif_ai_lab_scenario
    action:
      - event: mistermif_ai_lab_scenario_changed
        event_data:
          scenario: "{{ states('input_select.mistermif_ai_lab_scenario') }}"
          result: "{{ states('sensor.mistermif_ai_lab_esito_locale') }}"
"""


LAB_DASHBOARD_YAML = """\
title: Mistermif AI - Laboratorio energia
views:
  - title: Simulazione
    path: simulazione
    icon: mdi:test-tube
    cards:
      - type: markdown
        content: |
          ## Energy Safety Lab
          Questi comandi modificano solo sensori virtuali. Nessun carico reale,
          parametro inverter o stato batteria viene alterato.
      - type: entities
        title: Scenario virtuale
        entities:
          - input_select.mistermif_ai_lab_scenario
          - input_number.mistermif_ai_lab_available_amps
          - input_number.mistermif_ai_lab_battery_soc
          - input_number.mistermif_ai_lab_battery_current
          - input_number.mistermif_ai_lab_grid_power
          - input_number.mistermif_ai_lab_external_power
          - input_number.mistermif_ai_lab_solar_power
          - input_boolean.mistermif_ai_lab_external_parallel
          - input_boolean.mistermif_ai_lab_climate_on
          - input_boolean.mistermif_ai_lab_animals_on_board
      - type: entities
        title: Valutazione locale
        entities:
          - sensor.mistermif_ai_lab_limite_colonnina
          - sensor.mistermif_ai_lab_carico_colonnina
          - sensor.mistermif_ai_lab_margine_colonnina
          - sensor.mistermif_ai_lab_esito_locale
"""


LAB_HELPERS_YAML = """\
# Sorgente documentale: gli helper attivi sono riuniti nel package
# ../packages/mistermif_ai_energy_lab.yaml
helpers:
  scenario: input_select.mistermif_ai_lab_scenario
  battery_soc: input_number.mistermif_ai_lab_battery_soc
  battery_current: input_number.mistermif_ai_lab_battery_current
  grid_power: input_number.mistermif_ai_lab_grid_power
  external_power: input_number.mistermif_ai_lab_external_power
  solar_power: input_number.mistermif_ai_lab_solar_power
  available_amps: input_number.mistermif_ai_lab_available_amps
"""


LAB_FIXED_AUTOMATION_YAML = """\
# Sorgente documentale dell'automazione fissa inclusa nel package Energy Lab.
id: mistermif_ai_lab_scenario_trace
purpose: registra localmente il cambio dello scenario virtuale
real_services_called: false
protected_categories:
  - inverter
  - batteria
  - ventilazione
  - firmware
"""


LAB_DYNAMIC_POLICY_YAML = """\
name: energy_safety_dynamic_policy
version: 1
default_mode: simulation
lifecycle:
  - draft
  - simulation
  - shadow
  - active
allowed_actions:
  - turn_off_climate
  - send_notification
protected_actions:
  - request_inverter_sbu
  - change_inverter_parameter
  - change_bms_parameter
  - change_technical_ventilation
  - install_firmware
hard_rules:
  offline_data_never_triggers_action: true
  animal_mode_keeps_climate_priority: true
  active_requires_global_autonomy: true
  simulated_actions_never_call_home_assistant: true
"""
