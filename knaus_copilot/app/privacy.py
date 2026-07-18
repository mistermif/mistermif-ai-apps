from __future__ import annotations

import re
from typing import Any


REDACTIONS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[TOKEN RIMOSSO]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE), "[TOKEN RIMOSSO]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[EMAIL RIMOSSA]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)"), "[TELEFONO RIMOSSO]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP RIMOSSO]"),
    (
        re.compile(
            r"\b(?:lat(?:itude)?|lon(?:gitude)?)\s*[:=]\s*-?\d{1,3}(?:\.\d+)?",
            re.IGNORECASE,
        ),
        "[COORDINATA RIMOSSA]",
    ),
    (
        re.compile(r"(?<!\d)-?\d{1,2}\.\d{4,}\s*[,;/]\s*-?\d{1,3}\.\d{4,}(?!\d)"),
        "[COORDINATE RIMOSSE]",
    ),
)

SENSITIVE_ENTITY_FRAGMENTS = (
    "device_tracker",
    "person.",
    "geocoded_location",
    "latitude",
    "longitude",
    "gps",
    "position",
    "posizione",
    "address",
    "indirizzo",
    "ssid",
    "wifi",
    "ip_address",
    "phone",
    "telefono",
)

LOCAL_ONLY_MEMORY_CATEGORIES = {
    "viaggio",
    "percorso",
    "posizione",
    "campeggio",
    "piazzola",
    "profilo_mezzo",
    "persona",
    "contatto",
    "abitudine",
}


class PrivacyFilter:
    def sanitize_text(self, value: str) -> str:
        result = value
        for pattern, replacement in REDACTIONS:
            result = pattern.sub(replacement, result)
        return result

    def entity_is_sensitive(self, entity_id: str, name: str = "") -> bool:
        candidate = f"{entity_id} {name}".casefold()
        return any(fragment in candidate for fragment in SENSITIVE_ENTITY_FRAGMENTS)

    def sanitize_states(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for state in states:
            entity_id = str(state.get("entity_id", ""))
            name = str(state.get("name", ""))
            if self.entity_is_sensitive(entity_id, name):
                continue
            clean = dict(state)
            clean["entity_id"] = self.sanitize_text(entity_id)
            clean["name"] = self.sanitize_text(name)
            if isinstance(clean.get("state"), str):
                clean["state"] = self.sanitize_text(clean["state"])
            result.append(clean)
        return result

    def sanitize_memories(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for memory in memories:
            category = str(memory.get("category", "")).casefold()
            if category in LOCAL_ONLY_MEMORY_CATEGORIES:
                continue
            result.append(
                {
                    "category": self.sanitize_text(str(memory.get("category", ""))),
                    "title": self.sanitize_text(str(memory.get("title", ""))),
                    "content": self.sanitize_text(str(memory.get("content", ""))),
                }
            )
        return result
