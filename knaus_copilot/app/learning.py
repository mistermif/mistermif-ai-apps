from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from .memory import MemoryStore


ENERGY_TERMS = (
    "battery",
    "batteria",
    "soc",
    "solar",
    "solare",
    "pv",
    "photovolta",
    "fotovolta",
    "load",
    "carico",
    "power",
    "potenza",
    "current",
    "corrente",
)


@dataclass(frozen=True)
class LearningSummary:
    site_key: str
    samples: int
    confidence: float
    learned_sites: int
    averages: dict[str, float]


class ContextLearner:
    """Apprendimento locale di osservazioni e risultati, senza modificare il codice."""

    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.last_site_key = "unknown"

    def site_key(self, states: list[dict[str, Any]]) -> str:
        latitude = None
        longitude = None
        orientation = None
        for item in states:
            entity_id = str(item.get("entity_id", "")).casefold()
            attributes = item.get("attributes") or {}
            if entity_id.startswith("device_tracker.caravan"):
                latitude = self._number(attributes.get("latitude"))
                longitude = self._number(attributes.get("longitude"))
            if any(term in entity_id for term in ("heading", "orientamento", "bearing")):
                orientation = self._number(item.get("state"))

        if latitude is None or longitude is None:
            return "unknown"
        # Circa 110 m: separa le soste senza conservare coordinate nel nome pubblico.
        location = f"{latitude:.3f}:{longitude:.3f}"
        orientation_bucket = (
            "na" if orientation is None else str(int((orientation % 360) // 45))
        )
        digest = hashlib.sha256(f"{location}:{orientation_bucket}".encode()).hexdigest()
        return f"site-{digest[:12]}"

    def observe(self, states: list[dict[str, Any]]) -> LearningSummary:
        site_key = self.site_key(states)
        self.last_site_key = site_key
        if site_key == "unknown":
            return self.summary(site_key)
        metrics: dict[str, float] = {}
        for item in states:
            entity_id = str(item.get("entity_id", ""))
            candidate = f"{entity_id} {item.get('name', '')}".casefold()
            if not any(term in candidate for term in ENERGY_TERMS):
                continue
            value = self._number(item.get("state"))
            if value is not None:
                metrics[entity_id] = value

        payload = {
            "metrics": metrics,
            "hour": datetime.now(timezone.utc).hour,
        }
        self.memory.add_learning_observation(site_key, payload)
        return self.summary(site_key)

    def summary(self, site_key: str | None = None) -> LearningSummary:
        current = site_key or self.last_site_key
        observations = self.memory.recent_learning_observations(current)
        values: dict[str, list[float]] = {}
        for observation in observations:
            for entity_id, value in observation["payload"].get("metrics", {}).items():
                number = self._number(value)
                if number is not None:
                    values.setdefault(entity_id, []).append(number)
        averages = {
            entity_id: round(mean(series), 3)
            for entity_id, series in values.items()
            if series
        }
        samples = len(observations)
        return LearningSummary(
            site_key=current,
            samples=samples,
            confidence=(
                0.0
                if current == "unknown"
                else round(min(1.0, samples / 288), 3)
            ),
            learned_sites=self.memory.learning_site_count(),
            averages=averages,
        )

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
