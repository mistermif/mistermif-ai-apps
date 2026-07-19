from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class AlertLevel(str, Enum):
    EMERGENCY = "emergenza"
    URGENCY = "urgenza"
    ADVISORY = "allerta"


@dataclass(frozen=True)
class AlertDefinition:
    level: AlertLevel
    response_window_minutes: int | None
    intervention_required: bool
    description: str


ALERT_LEVELS = (
    AlertDefinition(
        AlertLevel.EMERGENCY,
        0,
        True,
        "Intervento immediato; escalation e notifiche ripetute.",
    ),
    AlertDefinition(
        AlertLevel.URGENCY,
        15,
        True,
        "Intervento richiesto entro 10-15 minuti.",
    ),
    AlertDefinition(
        AlertLevel.ADVISORY,
        None,
        False,
        "Nessun intervento necessario; prestare attenzione e monitorare.",
    ),
)


def public_alert_catalog() -> list[dict]:
    return [asdict(item) for item in ALERT_LEVELS]
