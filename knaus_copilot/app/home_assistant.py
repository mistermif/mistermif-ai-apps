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
        local_attributes = {
            key: attributes.get(key)
            for key in (
                "device_class",
                "state_class",
                "current_temperature",
                "temperature",
                "target_temp_high",
                "target_temp_low",
                "hvac_action",
                "percentage",
                "direction",
                "preset_mode",
            )
            if attributes.get(key) is not None
        }
        if entity_id.startswith("device_tracker.caravan"):
            local_attributes.update(
                {
                    key: attributes.get(key)
                    for key in ("latitude", "longitude", "gps_accuracy")
                    if attributes.get(key) is not None
                }
            )
        name = str(attributes.get("friendly_name", entity_id))
        return {
            "entity_id": entity_id,
            "state": state.get("state"),
            "name": name,
            "unit": attributes.get("unit_of_measurement"),
            "last_updated": state.get("last_updated"),
            "sensitive": self.policy.is_sensitive(entity_id, name),
            "attributes": local_attributes,
        }

    async def states(self) -> list[dict[str, Any]]:
        """Return the complete readable inventory for local reasoning.

        ``max_entities`` is intentionally not applied here: it is the maximum
        cloud context selected later by the agent, not an HA inventory limit.
        """
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
        return visible

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

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    async def location_snapshot(self) -> dict[str, Any]:
        """Read the caravan position locally without asking the language model."""
        states = await self.monitoring_states()
        latitude = None
        longitude = None
        latitude_entity = None
        longitude_entity = None
        updated = None
        accuracy = None

        for item in states:
            attributes = item.get("attributes") or {}
            lat = self._number(attributes.get("latitude"))
            lon = self._number(attributes.get("longitude"))
            if lat is None or lon is None:
                continue
            latitude, longitude = lat, lon
            latitude_entity = longitude_entity = item.get("entity_id")
            updated = item.get("last_updated")
            accuracy = self._number(attributes.get("gps_accuracy"))
            break

        if latitude is None or longitude is None:
            for item in states:
                candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
                if not any(anchor in candidate for anchor in ("gps", "caravan", "knaus", "posizion")):
                    continue
                value = self._number(item.get("state"))
                if value is None:
                    continue
                if latitude is None and any(term in candidate for term in ("latitude", "latitudine", "gps_lat")):
                    latitude = value
                    latitude_entity = item.get("entity_id")
                    updated = item.get("last_updated") or updated
                if longitude is None and any(term in candidate for term in ("longitude", "longitudine", "gps_lon")):
                    longitude = value
                    longitude_entity = item.get("entity_id")
                    updated = item.get("last_updated") or updated

        valid = (
            latitude is not None
            and longitude is not None
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
            and not (latitude == 0 and longitude == 0)
        )
        return {
            "available": valid,
            "latitude": latitude if valid else None,
            "longitude": longitude if valid else None,
            "accuracy_m": accuracy if valid else None,
            "last_updated": updated if valid else None,
            "entities": [
                entity
                for entity in dict.fromkeys((latitude_entity, longitude_entity))
                if entity
            ],
            "reason": None if valid else "coordinate_gps_non_disponibili",
        }

    async def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Resolve validated GPS coordinates to the nearest public OSM address."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "jsonv2",
                    "lat": f"{latitude:.7f}",
                    "lon": f"{longitude:.7f}",
                    "zoom": 18,
                    "addressdetails": 1,
                    "accept-language": "it",
                },
                headers={
                    "User-Agent": (
                        "mistermif-ai/1.5.5 "
                        "(Home Assistant caravan assistant; "
                        "https://github.com/mistermif/mistermif-ai-apps)"
                    )
                },
            )
            response.raise_for_status()
            data = response.json()
        address = data.get("address") or {}
        locality = next(
            (
                address.get(key)
                for key in ("village", "town", "city", "municipality", "county")
                if address.get(key)
            ),
            None,
        )
        return {
            "display_name": data.get("display_name"),
            "locality": locality,
            "address": address,
            "source": "OpenStreetMap Nominatim",
        }

    async def fridge_states(self) -> list[dict[str, Any]]:
        """Return a minimal local-only view of possible refrigerator devices."""
        terms = ("frigo", "fridge", "frigorif", "refriger", "ventol", "fan", "pwm")
        result = []
        for state in await self._raw_states():
            entity_id = str(state.get("entity_id", ""))
            attributes = state.get("attributes") or {}
            name = str(attributes.get("friendly_name", ""))
            candidate = f"{entity_id} {name}".casefold()
            unit = str(attributes.get("unit_of_measurement", "")).casefold()
            is_external_temperature = (
                unit in {"°c", "c", "°f", "f"}
                and any(word in candidate for word in ("estern", "external", "outdoor", "fuori"))
            )
            if not any(term in candidate for term in terms) and not is_external_temperature:
                continue
            result.append(
                {
                    "entity_id": entity_id,
                    "state": state.get("state"),
                    "name": name or entity_id,
                    "unit": attributes.get("unit_of_measurement"),
                    "last_updated": state.get("last_updated"),
                    "attributes": {
                        key: attributes.get(key)
                        for key in ("percentage", "min", "max", "step", "options")
                        if attributes.get(key) is not None
                    },
                }
            )
        return result

    @staticmethod
    def _dashboard_metric(
        states: list[dict[str, Any]],
        required: tuple[str, ...],
        preferred: tuple[str, ...],
        units: tuple[str, ...],
        excluded: tuple[str, ...] = (),
    ) -> dict[str, Any] | None:
        ranked = []
        for index, item in enumerate(states):
            candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
            unit = str(item.get("unit") or "").casefold()
            if not all(term in candidate for term in required):
                continue
            if excluded and any(term in candidate for term in excluded):
                continue
            if units and unit not in units:
                continue
            score = sum(
                (len(preferred) - position) * 3
                for position, term in enumerate(preferred)
                if term in candidate
            )
            ranked.append((-score, index, item))
        if not ranked:
            return None
        ranked.sort(key=lambda row: (row[0], row[1]))
        return ranked[0][2]

    async def dashboard_snapshot(self) -> dict[str, Any]:
        """Small read-only set for the onboard dashboard, independent of AI context."""
        visible = []
        for raw in await self._raw_states():
            item = self._visible_state(raw)
            if item is not None:
                visible.append(item)
        battery_terms = ("batter", "battery")
        temperature_units = ("°c", "c", "°f", "f")

        def best_any(required_groups, preferred, units, excluded=()):
            candidates = []
            for required in required_groups:
                item = self._dashboard_metric(visible, required, preferred, units, excluded)
                if item:
                    candidates.append(item)
            return candidates[0] if candidates else None

        def exact_entity(entity_ids):
            for entity_id in entity_ids:
                for item in visible:
                    if item.get("entity_id") == entity_id:
                        return item
            return None

        metrics = {
            "battery_soc": exact_entity(
                (
                    "sensor.livello_batteria_knaus",
                    "sensor.batteria_knaus_soc",
                )
            )
            or best_any(
                tuple((term,) for term in battery_terms),
                (
                    "batteria_knaus_soc",
                    "livello_batteria_knaus",
                    "battery_soc",
                    " soc",
                    "livello",
                ),
                ("%",),
                (
                    "link_quality",
                    "battery_health",
                    "intensita_del_segnale",
                    "signal",
                    "mistermif_ai_lab",
                    "smoke",
                ),
            ),
            "battery_current": best_any(
                tuple((term,) for term in battery_terms),
                ("batteria_knaus_corrente", "battery_current", "corrente", "current"),
                ("a",),
            ),
            "battery_voltage": best_any(
                tuple((term,) for term in battery_terms),
                ("batteria_knaus_tensione", "battery_voltage", "tensione", "voltage"),
                ("v",),
            ),
            "battery_power": best_any(
                tuple((term,) for term in battery_terms),
                ("batteria_knaus_potenza", "battery_power", "potenza", "power"),
                ("w", "kw"),
            ),
            "solar_power": best_any(
                (("pv",), ("solar",), ("fotovolta",), ("pannell",)),
                ("input_power", "potenza", "power", "produzione"),
                ("w", "kw"),
                ("daily", "giornal", "energy", "energia"),
            ),
            "grid_power": best_any(
                (("pzem",), ("grid",), ("rete",), ("utility",)),
                ("pzem_power", "potenza", "power", "input"),
                ("w", "kw"),
                ("voltage", "volt", "energy", "energia"),
            ),
            "grid_voltage": best_any(
                (("pzem",), ("grid",), ("rete",), ("utility",)),
                ("inverter_cooling_pzem_voltage", "pzem_grid_voltage", "voltage", "tensione"),
                ("v",),
                ("battery", "batter"),
            ),
            "grid_current": best_any(
                (("pzem",), ("grid",), ("rete",), ("utility",)),
                ("inverter_cooling_pzem_current", "pzem_grid_current", "current", "corrente"),
                ("a",),
                ("battery", "batter"),
            ),
            "load_power": best_any(
                (("load",), ("carico",), ("output_power",), ("potenza_uscita",)),
                ("pzem_load_power", "inverter_load", "output_power", "potenza"),
                ("w", "kw"),
                ("daily", "giornal", "energy", "energia"),
            ),
            "internal_temperature": best_any(
                (("temperatur",), ("temperature",)),
                ("intern", "caravan", "abitacolo"),
                temperature_units,
                ("frigo", "fridge", "inverter", "ester", "external"),
            ),
            "external_temperature": best_any(
                (("temperatur",), ("temperature",)),
                ("ester", "external", "outdoor", "fuori"),
                temperature_units,
                ("frigo", "fridge", "inverter"),
            ),
            "external_humidity": best_any(
                (("umid",), ("humidity",)),
                ("ester", "external", "outdoor", "fuori"),
                ("%",),
                ("intern", "frigo", "fridge"),
            ),
            "pressure": best_any(
                (("pression",), ("pressure",), ("barometr",)),
                ("barometr", "pressione atmosferica", "pressure"),
                ("hpa", "mbar", "pa"),
            ),
            "wind_speed": best_any(
                (("vento",), ("wind",)),
                ("veloc", "speed", "wind_speed"),
                ("km/h", "kmh", "m/s"),
                ("gust", "raffica", "direction", "direzione"),
            ),
            "wind_direction": best_any(
                (("vento",), ("wind",)),
                ("direzione", "direction", "bearing"),
                ("°", "deg"),
            ),
        }
        return {key: value for key, value in metrics.items()}

    async def health(self) -> dict:
        try:
            raw_states = await self._raw_states()
            states = [
                item
                for raw in raw_states
                if (item := self._visible_state(raw)) is not None
            ]
            sensitive = sum(bool(item.get("sensitive")) for item in states)
            return {
                "connected": bool(self.token),
                "total_entities": len(raw_states),
                "visible_entities": len(states),
                "sensitive_entities": sensitive,
                "cloud_context_limit": self.max_entities,
            }
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

    async def set_fridge_fan(self, entity_id: str, percentage: float) -> dict:
        if not self.token:
            raise RuntimeError("Home Assistant non è collegato")
        if not self.policy.can_control_fridge(entity_id):
            raise PermissionError("Comando ventola frigorifero non autorizzato")
        percentage = max(0.0, min(100.0, float(percentage)))
        domain = entity_id.split(".", 1)[0]
        if domain == "fan":
            service = "set_percentage"
            data = {"entity_id": entity_id, "percentage": round(percentage)}
        elif domain in {"number", "input_number"}:
            service = "set_value"
            data = {"entity_id": entity_id, "value": round(percentage, 1)}
        else:
            raise PermissionError("Il comando PWM deve essere fan.* o number.*")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self.base_url}/services/{domain}/{service}",
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()
        return {
            "ok": True,
            "entity_id": entity_id,
            "percentage": percentage,
            "service": f"{domain}.{service}",
        }

    async def set_fridge_parameter(self, entity_id: str, value: float) -> dict:
        if not self.token:
            raise RuntimeError("Home Assistant non è collegato")
        if not self.policy.can_control_fridge(entity_id):
            raise PermissionError("Parametro frigorifero non autorizzato")
        domain = entity_id.split(".", 1)[0]
        if domain == "select":
            unit = "%" if "pwm" in entity_id else "°C"
            service = "select_option"
            data = {"entity_id": entity_id, "option": f"{round(value)} {unit}"}
        elif domain in {"number", "input_number"}:
            service = "set_value"
            data = {"entity_id": entity_id, "value": round(float(value), 1)}
        else:
            raise PermissionError("Parametro frigo non supportato")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{self.base_url}/services/{domain}/{service}",
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()
        return {"ok": True, "entity_id": entity_id, "value": value, "service": f"{domain}.{service}"}
