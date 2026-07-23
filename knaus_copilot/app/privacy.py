from __future__ import annotations

import re
from typing import Any


REDACTIONS = (
    (
        re.compile(
            r"\b(?:api[_ -]?key|token|password|secret)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        "[SEGRETO RIMOSSO]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[TOKEN RIMOSSO]"),
    (re.compile(r"\bgsk_[A-Za-z0-9_-]{16,}\b"), "[TOKEN RIMOSSO]"),
    (re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"), "[TOKEN RIMOSSO]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE), "[TOKEN RIMOSSO]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[EMAIL RIMOSSA]"),
    (
        re.compile(
            r"(?<![\d.])(?!\d{1,3}\.\d{4,}\b)(?:\+?\d[\d .()-]{7,}\d)(?![\d.])"
        ),
        "[TELEFONO RIMOSSO]",
    ),
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
    "external_ip",
    "public_ip",
    "wan_ip",
    "ip_esterno",
    "indirizzo_ip",
    "mac_address",
    "bssid",
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

SECRET_ATTRIBUTE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "passwd",
    "secret",
    "authorization",
    "credential",
    "credentials",
    "ssid",
    "bssid",
    "ip_address",
    "mac_address",
    "email",
    "phone",
    "telephone",
    "telefono",
}

LOCATION_ATTRIBUTE_KEYS = {
    "latitude",
    "longitude",
    "gps_accuracy",
    "address",
    "indirizzo",
}


class PrivacyFilter:
    def __init__(self, allow_location: bool = False):
        self.allow_location = allow_location

    def sanitize_text(self, value: str) -> str:
        result = value
        for index, (pattern, replacement) in enumerate(REDACTIONS):
            if self.allow_location and index >= len(REDACTIONS) - 2:
                continue
            result = pattern.sub(replacement, result)
        return result

    def entity_is_sensitive(self, entity_id: str, name: str = "") -> bool:
        candidate = f"{entity_id} {name}".casefold()
        domain, _, object_id = entity_id.casefold().partition(".")
        if domain in {"camera", "image", "person"}:
            return True
        if domain == "device_tracker" and not object_id.startswith("caravan"):
            return True
        if self.allow_location and any(
            fragment in candidate
            for fragment in (
                "device_tracker",
                "latitude",
                "longitude",
                "gps",
                "position",
                "posizione",
                "address",
                "indirizzo",
            )
        ):
            return False
        normalized_tokens = {
            token
            for token in candidate.replace(".", "_").replace("-", "_").split("_")
            if token
        }
        if "ip" in normalized_tokens:
            return True
        return any(fragment in candidate for fragment in SENSITIVE_ENTITY_FRAGMENTS)

    def sanitize_value(self, value: Any, key: str = "") -> Any:
        normalized_key = key.casefold().replace("-", "_").replace(" ", "_")
        if normalized_key in SECRET_ATTRIBUTE_KEYS:
            return "[DATO SENSIBILE RIMOSSO]"
        if (
            not self.allow_location
            and normalized_key in LOCATION_ATTRIBUTE_KEYS
        ):
            return "[POSIZIONE RIMOSSA]"
        if isinstance(value, str):
            return self.sanitize_text(value)
        if isinstance(value, dict):
            return {
                str(child_key): self.sanitize_value(child_value, str(child_key))
                for child_key, child_value in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.sanitize_value(item, key) for item in value]
        return value

    def sanitize_states(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for state in states:
            entity_id = str(state.get("entity_id", ""))
            name = str(state.get("name", ""))
            if self.entity_is_sensitive(entity_id, name):
                continue
            clean = {
                key: state.get(key)
                for key in (
                    "entity_id",
                    "state",
                    "name",
                    "unit",
                    "last_updated",
                    "attributes",
                )
            }
            clean["entity_id"] = self.sanitize_text(entity_id)
            clean["name"] = self.sanitize_text(name)
            if isinstance(clean.get("state"), str):
                clean["state"] = self.sanitize_text(clean["state"])
            clean["attributes"] = self.sanitize_value(
                clean.get("attributes") or {},
                "attributes",
            )
            result.append(clean)
        return result

    def sanitize_memories(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for memory in memories:
            category = str(memory.get("category", "")).casefold()
            if not self.allow_location and category in LOCAL_ONLY_MEMORY_CATEGORIES:
                continue
            result.append(
                {
                    "category": self.sanitize_text(str(memory.get("category", ""))),
                    "title": self.sanitize_text(str(memory.get("title", ""))),
                    "content": self.sanitize_text(str(memory.get("content", ""))),
                }
            )
        return result
