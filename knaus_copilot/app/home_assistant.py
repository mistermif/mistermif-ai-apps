from __future__ import annotations

from typing import Any

import httpx

from .permissions import PermissionPolicy


class HomeAssistantClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        policy: PermissionPolicy,
        max_entities: int = 80,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.policy = policy
        self.max_entities = max_entities

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _raw_states(self) -> list[dict[str, Any]]:
        if not self.token:
            return []
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                f"{self.base_url}/states", headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    def _visible_state(self, state: dict[str, Any]) -> dict[str, Any] | None:
        entity_id = str(state.get("entity_id", ""))
        if not self.policy.can_read(entity_id):
            return None
        attributes = state.get("attributes") or {}
        local_attributes = {}
        if entity_id.startswith("device_tracker.caravan"):
            local_attributes = {
                key: attributes.get(key)
                for key in ("latitude", "longitude", "gps_accuracy")
                if attributes.get(key) is not None
            }
        return {
            "entity_id": entity_id,
            "state": state.get("state"),
            "name": attributes.get("friendly_name", entity_id),
            "unit": attributes.get("unit_of_measurement"),
            "last_updated": state.get("last_updated"),
            "sensitive": self.policy.is_sensitive(entity_id),
            "attributes": local_attributes,
        }

    async def states(self) -> list[dict[str, Any]]:
        raw_states = await self._raw_states()

        visible = []
        for state in raw_states:
            item = self._visible_state(state)
            if item is not None:
                visible.append(item)
        visible.sort(
            key=lambda item: (
                not str(item["entity_id"]).startswith("device_tracker.caravan"),
                str(item["entity_id"]),
            )
        )
        return visible[: self.max_entities]

    async def monitoring_states(self) -> list[dict[str, Any]]:
        """Return only local entities useful to weather and travel engines."""
        terms = (
            "gps",
            "meteo",
            "weather",
            "pression",
            "baro",
            "vento",
            "wind",
            "piogg",
            "rain",
            "fulmin",
            "lightning",
            "grandine",
            "hail",
            "temperatura",
            "temperature",
            "umid",
            "humidity",
            "rischio",
        )
        result = []
        for state in await self._raw_states():
            entity_id = str(state.get("entity_id", ""))
            name = str((state.get("attributes") or {}).get("friendly_name", ""))
            candidate = f"{entity_id} {name}".casefold()
            if not (
                entity_id.startswith("device_tracker.caravan")
                or any(term in candidate for term in terms)
            ):
                continue
            item = self._visible_state(state)
            if item is not None:
                result.append(item)
        return result

    async def health(self) -> dict:
        try:
            states = await self.states()
            return {"connected": bool(self.token), "visible_entities": len(states)}
        except (httpx.HTTPError, ValueError) as exc:
            return {"connected": False, "error": str(exc)}

    async def turn_off_climate(self) -> dict:
        entity_id = self.policy.climate_entity
        if not self.token:
            raise RuntimeError("Home Assistant non è collegato")
        if not self.policy.can_control_entity(entity_id):
            raise PermissionError("Climatizzatore non autorizzato")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self.base_url}/services/climate/turn_off",
                headers=self.headers,
                json={"entity_id": entity_id},
            )
            response.raise_for_status()
        return {"ok": True, "entity_id": entity_id, "service": "climate.turn_off"}

    async def send_notification(
        self,
        service_name: str,
        title: str,
        message: str,
    ) -> dict:
        if not self.token:
            raise RuntimeError("Home Assistant non è collegato")
        if not self.policy.can_execute("send_notification"):
            raise PermissionError("Invio notifiche non autorizzato")
        domain, service = service_name.split(".", 1)
        if domain != "notify" or not service:
            raise PermissionError("Servizio notifiche non valido")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self.base_url}/services/{domain}/{service}",
                headers=self.headers,
                json={"title": title, "message": message},
            )
            response.raise_for_status()
        return {"ok": True, "service": service_name}

    async def send_telegram(
        self,
        targets: tuple[str, ...],
        message: str,
    ) -> dict:
        if not targets:
            return {"ok": False, "skipped": "nessun destinatario Telegram"}
        if not self.token:
            raise RuntimeError("Home Assistant non è collegato")
        if not self.policy.can_execute("send_notification"):
            raise PermissionError("Invio notifiche non autorizzato")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self.base_url}/services/telegram_bot/send_message",
                headers=self.headers,
                json={"target": list(targets), "message": message},
            )
            response.raise_for_status()
        return {"ok": True, "service": "telegram_bot.send_message"}
