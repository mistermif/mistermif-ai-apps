from __future__ import annotations

import re
from dataclasses import asdict, replace
from typing import Any

from .automation_lab import LabSnapshot, SCENARIOS, evaluate_snapshot, run_scenario


SIMULATION_DOMAINS = (
    "batter",
    "soc",
    "solare",
    "fotovolta",
    "pv",
    "colonnina",
    "pzem",
    "presa esterna",
    "clima",
    "climatizz",
    "animali",
    "cani",
    "sensori",
    "energia",
    "inverter",
)

EXPECTED_SCENARIOS = {
    "sensori_offline": "wait_for_valid_data",
    "batteria_critica_senza_sole": "protect_battery",
    "batteria_bassa_in_recupero": "observe_recovery",
    "colonnina_6a_quasi_limite": "prevent_shore_trip",
    "colonnina_10a_presa_esterna": "prevent_shore_trip",
    "animali_batteria_bassa": "protect_climate_and_escalate",
}

ACTION_LABELS = {
    "turn_off_climate": "spegnimento del climatizzatore",
    "send_notification": "notifica all'equipaggio",
    "request_inverter_sbu": "richiesta di passaggio SBU (protetta)",
}


def is_simulation_request(message: str) -> bool:
    text = message.casefold()
    if any(token in text for token in ("simula", "simulazione", "self-check", "self check")):
        return True
    if any(token in text for token in ("test completo", "controllo completo")):
        return "mistermif" in text or any(domain in text for domain in SIMULATION_DOMAINS)
    return "test" in text and any(domain in text for domain in SIMULATION_DOMAINS)


def is_full_self_check_request(message: str) -> bool:
    text = message.casefold()
    return any(
        token in text
        for token in (
            "test completo",
            "controllo completo",
            "tutte le simulazioni",
            "tutti gli scenari",
            "self-check",
            "self check",
            "verifica tutto",
        )
    )


def _number(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _semantic_base(message: str) -> tuple[LabSnapshot, str]:
    text = message.casefold()
    if "sensor" in text and any(word in text for word in ("offline", "unknown", "unavailable")):
        scenario = SCENARIOS["sensori_offline"]
    elif any(word in text for word in ("animali", "cani", "gatti")):
        scenario = SCENARIOS["animali_batteria_bassa"]
    elif "presa esterna" in text or ("10 a" in text and "colonnina" in text):
        scenario = SCENARIOS["colonnina_10a_presa_esterna"]
    elif "colonnina" in text or "pzem" in text:
        scenario = SCENARIOS["colonnina_6a_quasi_limite"]
    elif any(word in text for word in ("recuper", "sole in crescita", "ricarica solare")):
        scenario = SCENARIOS["batteria_bassa_in_recupero"]
    elif any(word in text for word in ("batteria", "soc")):
        scenario = SCENARIOS["batteria_critica_senza_sole"]
    else:
        scenario = SCENARIOS["sensori_offline"]
    return scenario.snapshot, scenario.label


def snapshot_from_message(message: str) -> tuple[LabSnapshot, list[str], str]:
    text = message.casefold()
    base, base_label = _semantic_base(message)
    values = asdict(base)
    recognized: set[str] = set()

    soc = _number(
        text,
        (
            r"(?:batteria|soc)\s*(?:al|a|=|del)?\s*(\d+(?:[.,]\d+)?)\s*%",
            r"(\d+(?:[.,]\d+)?)\s*%\s*(?:di\s+)?(?:batteria|soc)",
        ),
    )
    if soc is not None:
        values["battery_soc"] = max(0.0, min(100.0, soc))
        recognized.add("SOC")

    amps = _number(
        text,
        (
            r"(?:colonnina|rete|disponibil\w*)[^\d]{0,18}(\d+(?:[.,]\d+)?)\s*a(?:mpere)?\b",
            r"(\d+(?:[.,]\d+)?)\s*a(?:mpere)?\b[^.]{0,18}(?:colonnina|disponibil\w*)",
        ),
    )
    if amps is not None:
        values["available_amps"] = max(3, min(16, int(round(amps))))
        recognized.add("ampere colonnina")

    grid_power = _number(
        text,
        (
            r"(?:pzem|carico(?: totale)?|consumo totale|consumo caravan|rete)[^\d]{0,20}(\d+(?:[.,]\d+)?)\s*w",
            r"(\d+(?:[.,]\d+)?)\s*w[^.]{0,20}(?:pzem|caravan|dalla rete)",
        ),
    )
    if grid_power is None and "presa esterna" not in text:
        grid_power = _number(text, (r"(?:fornello|induzione)[^\d]{0,18}(\d+(?:[.,]\d+)?)\s*w",))
    if grid_power is not None:
        values["grid_power"] = max(0.0, grid_power)
        recognized.add("potenza PZEM/rete")

    external_power = _number(
        text,
        (
            r"(?:presa esterna|fornello esterno)[^\d]{0,20}(\d+(?:[.,]\d+)?)\s*w",
            r"(\d+(?:[.,]\d+)?)\s*w[^.]{0,20}(?:presa esterna|fornello esterno)",
        ),
    )
    if external_power is not None:
        values["external_power"] = max(0.0, external_power)
        values["external_socket_parallel"] = True
        recognized.add("potenza presa esterna")

    solar_power = _number(
        text,
        (
            r"(?:solare|fotovoltaico|fotovoltaica|pv|pannelli)[^\d]{0,20}(\d+(?:[.,]\d+)?)\s*w",
            r"(\d+(?:[.,]\d+)?)\s*w[^.]{0,20}(?:solare|fotovoltaico|pv|pannelli)",
        ),
    )
    if solar_power is not None:
        values["solar_power"] = max(0.0, solar_power)
        recognized.add("produzione solare")
    elif any(token in text for token in ("senza sole", "niente sole", "nessuna produzione", "pv spent")):
        values["solar_power"] = 0.0
        recognized.add("assenza di produzione solare")

    battery_current = _number(
        text,
        (
            r"(?:corrente batteria|batteria)[^\d+-]{0,16}([+-]?\d+(?:[.,]\d+)?)\s*a\b",
            r"corrente[^\d+-]{0,12}([+-]?\d+(?:[.,]\d+)?)\s*a\b",
            r"([+-]?\d+(?:[.,]\d+)?)\s*a\b[^.]{0,20}(?:dalla batteria|in batteria)",
        ),
    )
    if battery_current is not None:
        if battery_current > 0 and any(token in text for token in ("assorbe", "scarica", "preleva", "dalla batteria")):
            battery_current = -battery_current
        values["battery_current"] = battery_current
        recognized.add("corrente batteria")

    trend = _number(
        text,
        (
            r"(?:scende|cala|perde)[^\d]{0,12}(\d+(?:[.,]\d+)?)\s*%\s*(?:/|all['’]?ora|ora)",
            r"trend[^\d+-]{0,10}([+-]?\d+(?:[.,]\d+)?)\s*%",
        ),
    )
    if trend is not None:
        values["battery_trend_percent_per_hour"] = -abs(trend) if any(token in text for token in ("scende", "cala", "perde")) else trend
        recognized.add("tendenza SOC")

    hour = _number(text, (r"(?:alle|ore)\s*(\d{1,2})(?::\d{2})?",))
    if hour is not None:
        values["hour"] = max(0, min(23, int(hour)))
        recognized.add("orario")

    if any(token in text for token in ("sensori offline", "sensore offline", "dati unavailable", "dati unknown")):
        values["sensors_available"] = False
        recognized.add("sensori offline")
    elif "sensori online" in text or "dati validi" in text:
        values["sensors_available"] = True
        recognized.add("sensori disponibili")

    if any(token in text for token in ("clima spento", "climatizzatore spento", "clima disattivato")):
        values["climate_on"] = False
        recognized.add("clima spento")
    elif any(token in text for token in ("clima acceso", "climatizzatore acceso", "clima attivo")):
        values["climate_on"] = True
        recognized.add("clima acceso")

    if any(token in text for token in ("animali a bordo", "cani a bordo", "cane a bordo", "gatti a bordo")):
        values["animals_on_board"] = True
        recognized.add("animali a bordo")
    elif any(token in text for token in ("senza animali", "nessun animale", "cani non a bordo")):
        values["animals_on_board"] = False
        recognized.add("nessun animale a bordo")

    if any(token in text for token in ("ricarica esterna attiva", "generatore acceso", "caricabatterie acceso")):
        values["external_charge"] = True
        recognized.add("ricarica esterna")
    elif any(token in text for token in ("nessuna ricarica", "senza ricarica", "generatore spento")):
        values["external_charge"] = False
        recognized.add("nessuna ricarica esterna")

    if "presa esterna" in text or "in parallelo" in text:
        values["external_socket_parallel"] = True

    snapshot = replace(base, **values)
    assumptions = []
    if not recognized:
        assumptions.append(f"Ho usato lo scenario noto: {base_label}.")
    else:
        assumptions.append(
            f"I valori non specificati restano quelli prudenziali dello scenario base: {base_label}."
        )
    return snapshot, assumptions, base_label


def assess_result(
    snapshot: LabSnapshot,
    result: dict[str, Any],
    *,
    expected_decision: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    safety = result.get("safety", {})
    isolated = (
        result.get("executed_actions") == []
        and not safety.get("real_services_called", True)
        and not safety.get("inverter_parameters_mutated", True)
        and not safety.get("battery_discharged_by_test", True)
    )
    add("isolamento", isolated, "nessun servizio reale, parametro inverter o batteria coinvolto")

    if expected_decision:
        actual = result.get("decision")
        add(
            "decisione attesa",
            actual == expected_decision,
            f"attesa {expected_decision}, ottenuta {actual}",
        )

    if not snapshot.sensors_available:
        safe_offline = not result.get("allowed_actions") and not result.get("conclusive")
        add("dati mancanti", safe_offline, "i dati offline non devono produrre comandi")

    if snapshot.animals_on_board and snapshot.battery_soc <= 30:
        climate_protected = "turn_off_climate" not in result.get("allowed_actions", [])
        add("protezione animali", climate_protected, "il clima non deve essere spento automaticamente")

    charging_recovery = (
        snapshot.external_charge
        or snapshot.solar_power >= 250
        or snapshot.battery_current >= 8
        or snapshot.battery_trend_percent_per_hour >= 1
    )
    if snapshot.battery_soc <= 30 and charging_recovery and not snapshot.animals_on_board:
        no_early_shutdown = "turn_off_climate" not in result.get("allowed_actions", [])
        add("recupero energetico", no_early_shutdown, "nessuno spegnimento prematuro durante un recupero reale")

    limit_watts = snapshot.available_amps * 230
    observed = snapshot.grid_power + (
        snapshot.external_power if snapshot.external_socket_parallel else 0
    )
    if limit_watts and observed / limit_watts >= 0.92 and snapshot.battery_soc > 30:
        trip_prevention = result.get("decision") == "prevent_shore_trip"
        add("protezione colonnina", trip_prevention, "il carico vicino al limite deve essere riconosciuto")

    failures = [item for item in checks if not item["passed"]]
    return {
        "passed": not failures,
        "checks": checks,
        "failures": failures,
    }


def _action_text(actions: list[str]) -> str:
    if not actions:
        return "nessuna"
    return ", ".join(ACTION_LABELS.get(action, action) for action in actions)


def _format_snapshot(snapshot: LabSnapshot) -> str:
    external = (
        f", presa esterna {snapshot.external_power:.0f} W in parallelo"
        if snapshot.external_socket_parallel
        else ""
    )
    return (
        f"SOC {snapshot.battery_soc:g}%, batteria {snapshot.battery_current:g} A, "
        f"PZEM/rete {snapshot.grid_power:g} W{external}, solare "
        f"{snapshot.solar_power:g} W, colonnina {snapshot.available_amps} A, "
        f"clima {'acceso' if snapshot.climate_on else 'spento'}, "
        f"animali {'a bordo' if snapshot.animals_on_board else 'non dichiarati'}"
    )


def run_conversational_simulation(message: str) -> dict[str, Any] | None:
    if not is_simulation_request(message):
        return None
    if is_full_self_check_request(message):
        return run_full_self_check()
    if not any(domain in message.casefold() for domain in SIMULATION_DOMAINS):
        return {
            "kind": "clarification",
            "answer": (
                "Certo. Descrivimi la condizione energetica da simulare indicando "
                "quello che conosci: SOC, corrente batteria, watt PZEM, watt della "
                "presa esterna, produzione solare, ampere della colonnina, clima, "
                "orario e presenza di animali. I valori mancanti saranno dichiarati "
                "come assunzioni e nessun comando reale verrà eseguito."
            ),
        }

    snapshot, assumptions, base_label = snapshot_from_message(message)
    result = evaluate_snapshot(snapshot)
    assessment = assess_result(snapshot, result)
    result["simulation_input"] = asdict(snapshot)
    result["self_assessment"] = assessment
    verdict = "COERENTE" if assessment["passed"] else "DA CORREGGERE"
    checks = "; ".join(
        f"{'OK' if item['passed'] else 'ERRORE'} {item['name']}"
        for item in assessment["checks"]
    )
    protected = _action_text(result.get("protected_recommendations", []))
    answer = "\n".join(
        (
            f"SIMULAZIONE CONVERSAZIONALE — {verdict}",
            f"Dati virtuali interpretati: {_format_snapshot(snapshot)}.",
            f"Decisione: {result['severity'].upper()} · {result['decision']}.",
            f"Motivo: {result['reason']}",
            f"Azioni che proporrebbe: {_action_text(result['allowed_actions'])}.",
            f"Raccomandazioni protette: {protected}.",
            f"Autoverifica: {checks}.",
            "Azioni reali eseguite: 0. Batteria reale utilizzata: 0%.",
            assumptions[0],
        )
    )
    return {
        "kind": "single",
        "base_scenario": base_label,
        "snapshot": asdict(snapshot),
        "result": result,
        "assessment": assessment,
        "answer": answer,
    }


def run_full_self_check() -> dict[str, Any]:
    items = []
    for scenario_id, expected_decision in EXPECTED_SCENARIOS.items():
        result = run_scenario(scenario_id)
        snapshot = SCENARIOS[scenario_id].snapshot
        assessment = assess_result(
            snapshot,
            result,
            expected_decision=expected_decision,
        )
        result["self_assessment"] = assessment
        items.append(
            {
                "scenario_id": scenario_id,
                "label": SCENARIOS[scenario_id].label,
                "result": result,
                "assessment": assessment,
            }
        )
    passed = sum(1 for item in items if item["assessment"]["passed"])
    all_passed = passed == len(items)
    lines = [
        f"SELF-CHECK COMPLETO — {'TUTTO COERENTE' if all_passed else 'ANOMALIE RILEVATE'}",
        f"Scenari superati: {passed}/{len(items)}.",
    ]
    for item in items:
        result = item["result"]
        mark = "OK" if item["assessment"]["passed"] else "ERRORE"
        lines.append(
            f"{mark} · {item['label']}: {result['severity']} / {result['decision']}"
        )
    lines.extend(
        (
            "Autoverifica globale: isolamento reale, dati offline, recupero solare, limite colonnina e protezione animali controllati.",
            "Azioni reali eseguite: 0. Batteria reale utilizzata: 0%.",
        )
    )
    return {
        "kind": "full",
        "passed": all_passed,
        "passed_count": passed,
        "total": len(items),
        "items": items,
        "answer": "\n".join(lines),
    }
