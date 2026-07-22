from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx

from .home_assistant import HomeAssistantClient
from .memory import MemoryStore
from .cloud_usage import CloudBudgetExceeded, CloudUsage


logger = logging.getLogger("mistermif-ai.weather")
SEVERITY_RANK = {"nessuna": 0, "allerta": 1, "urgenza": 2, "emergenza": 3}
WeatherAIEvaluator = Callable[
    [dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]
]


@dataclass(frozen=True)
class WeatherRisk:
    kind: str
    severity: str
    score: int
    source: str
    detail: str


class WeatherMonitor:
    """Local-first weather supervisor with bounded AI escalation."""

    def __init__(
        self,
        memory: MemoryStore,
        ha: HomeAssistantClient,
        notification_service: str,
        telegram_targets: tuple[str, ...] = (),
        dpc_enabled: bool = True,
        windy_api_key: str = "",
        ai_evaluator: WeatherAIEvaluator | None = None,
        ai_usage: CloudUsage | None = None,
    ):
        self.memory = memory
        self.ha = ha
        self.notification_service = notification_service
        self.telegram_targets = telegram_targets
        self.dpc_enabled = dpc_enabled
        self.windy_api_key = windy_api_key
        self.ai_evaluator = ai_evaluator
        self.ai_usage = ai_usage

    async def monitor_once(self) -> dict[str, Any]:
        states = await self.ha.monitoring_states()
        location_info: dict[str, Any] = {}
        try:
            location_info = await self.ha.location_snapshot()
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError):
            logger.exception("Lettura GPS validata non disponibile per il meteo")
        if location_info.get("available"):
            location = (
                float(location_info["latitude"]),
                float(location_info["longitude"]),
            )
        else:
            location = self._location(states)
        risks = self.analyse_local(states)
        sources = {"sensori_home_assistant": "ok" if states else "non disponibili"}
        local_observation = self.extract_local_observation(states)
        local_trend = self.record_local_observation(local_observation)
        risks.extend(self.analyse_local_trend(local_trend))
        sources["sensori_esterni"] = (
            "ok" if local_observation else "non disponibili"
        )

        if location is not None:
            latitude, longitude = location
            sources["posizione_gps"] = "ok"
            try:
                forecast = await self.fetch_open_meteo(latitude, longitude)
                risks.extend(self.analyse_open_meteo(forecast))
                forecast_summary = self.forecast_summary(forecast)
                sources["open_meteo_multimodello"] = "ok"
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                logger.exception("Open-Meteo non disponibile")
                forecast_summary = {}
                sources["open_meteo_multimodello"] = "errore"
            if self.dpc_enabled and self._inside_italy(latitude, longitude):
                try:
                    hrd = await self.fetch_dpc_hrd(latitude, longitude)
                    dpc_risks = self.analyse_dpc_hrd(hrd)
                    risks.extend(dpc_risks)
                    sources["radar_dpc_hrd"] = (
                        "fenomeno rilevato" if dpc_risks else "nessun fenomeno puntuale"
                    )
                except (httpx.HTTPError, ValueError, TypeError):
                    logger.exception("Radar-DPC non disponibile")
                    sources["radar_dpc_hrd"] = "errore"
            else:
                sources["radar_dpc_hrd"] = "fuori Italia o disattivato"
            if self.windy_api_key:
                try:
                    windy = await self.fetch_windy(latitude, longitude)
                    risks.extend(self.analyse_windy(windy))
                    sources["windy_professional"] = "ok"
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    logger.exception("Windy Point Forecast non disponibile")
                    sources["windy_professional"] = "errore"
            else:
                sources["windy_professional"] = "non configurato"
        else:
            forecast_summary = {}
            sources["posizione_gps"] = "non disponibile"

        deterministic = self.assess(risks)
        assessment = dict(deterministic)
        ai_review = None
        if self.ai_evaluator is None or self.ai_usage is None:
            sources["gemini_meteo"] = "non configurato"
        elif not self.should_consult_ai(deterministic):
            sources["gemini_meteo"] = "non chiamato: quadro stabile o sereno"
        else:
            try:
                self.ai_usage.consume(automatic=True)
                ai_context = dict(deterministic)
                ai_context["location"] = (
                    {
                        "latitude": location[0],
                        "longitude": location[1],
                        "accuracy_m": location_info.get("accuracy_m"),
                    }
                    if location is not None
                    else None
                )
                ai_context["forecast"] = forecast_summary
                ai_review = await self.ai_evaluator(
                    ai_context,
                    {**local_observation, "trend": local_trend},
                )
                sources["gemini_meteo"] = "valutazione eseguita"
                ai_rank = SEVERITY_RANK.get(str(ai_review.get("severity")), 0)
                current_rank = SEVERITY_RANK.get(deterministic["severity"], 0)
                if (
                    ai_review.get("worsening")
                    and float(ai_review.get("confidence", 0)) >= 0.65
                    and ai_rank > current_rank
                    and current_rank > 0
                ):
                    risks.append(
                        WeatherRisk(
                            "valutazione_ai",
                            "urgenza" if ai_rank >= 2 else "allerta",
                            min(79, max(55, deterministic["score"] + 10)),
                            "Gemini",
                            str(ai_review.get("summary") or "peggioramento probabile"),
                        )
                    )
                    assessment = self.assess(risks)
            except CloudBudgetExceeded:
                sources["gemini_meteo"] = "limite giornaliero raggiunto"
            except (httpx.HTTPError, RuntimeError, ValueError, TypeError):
                logger.exception("Valutazione meteo Gemini non disponibile")
                sources["gemini_meteo"] = "errore: controllo locale attivo"
        assessment["checked_at"] = datetime.now(timezone.utc).isoformat()
        movement = self._movement(states)
        assessment["moving"] = movement
        assessment["sources"] = sources
        assessment["local_observation"] = local_observation
        assessment["local_trend"] = local_trend
        assessment["forecast"] = forecast_summary
        assessment["deterministic"] = deterministic
        assessment["gemini_review"] = ai_review
        assessment["gemini_budget"] = (
            self.ai_usage.snapshot() if self.ai_usage is not None else None
        )
        should_notify, reason = self.should_notify(assessment)
        assessment["notification_reason"] = reason
        assessment["notified"] = False
        if should_notify:
            await self._notify(assessment)
            assessment["notified"] = True
        self.memory.set_json_setting("weather_monitor_state", assessment)
        return assessment

    def should_consult_ai(self, current: dict[str, Any]) -> bool:
        if SEVERITY_RANK.get(str(current.get("severity")), 0) == 0:
            return False
        previous_state = self.memory.get_json_setting("weather_monitor_state") or {}
        previous = previous_state.get("deterministic") or previous_state
        current_rank = SEVERITY_RANK.get(str(current.get("severity")), 0)
        previous_rank = SEVERITY_RANK.get(str(previous.get("severity")), 0)
        if previous_rank == 0 or current_rank > previous_rank:
            return True
        if set(current.get("kinds") or []) - set(previous.get("kinds") or []):
            return True
        return int(current.get("score") or 0) >= int(previous.get("score") or 0) + 10

    async def fetch_open_meteo(self, latitude: float, longitude: float) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,precipitation,rain,wind_speed_10m,"
                "wind_direction_10m,wind_gusts_10m,surface_pressure"
            ),
            "hourly": (
                "weather_code,precipitation_probability,precipitation,rain,"
                "showers,wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
                "cape,temperature_2m,relative_humidity_2m"
            ),
            "forecast_hours": 12,
            "timezone": "auto",
            "wind_speed_unit": "kmh",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast", params=params
            )
            response.raise_for_status()
            return response.json()

    @classmethod
    def forecast_summary(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a compact, presentation-safe weather snapshot."""
        current = payload.get("current") or {}
        hourly = payload.get("hourly") or {}

        def first(key: str) -> float | None:
            values = hourly.get(key) or []
            return cls._number(values[0]) if values else None

        def number(key: str, hourly_key: str | None = None) -> float | None:
            value = cls._number(current.get(key))
            return value if value is not None else first(hourly_key or key)

        code_value = number("weather_code")
        code = int(code_value) if code_value is not None else None
        direction = number("wind_direction_10m")
        probability_values = [
            cls._number(value) or 0
            for value in (hourly.get("precipitation_probability") or [])[:8]
        ]
        gust_values = [
            cls._number(value) or 0
            for value in (hourly.get("wind_gusts_10m") or [])[:8]
        ]
        return {
            "condition": cls.weather_label(code),
            "weather_code": code,
            "temperature_c": number("temperature_2m"),
            "apparent_temperature_c": number("apparent_temperature"),
            "humidity_percent": number("relative_humidity_2m"),
            "pressure_hpa": number("surface_pressure"),
            "wind_speed_kmh": number("wind_speed_10m"),
            "wind_direction_deg": direction,
            "wind_direction": cls.compass_direction(direction),
            "wind_gust_kmh": number("wind_gusts_10m"),
            "max_gust_8h_kmh": max(gust_values, default=0),
            "precipitation_probability_8h": max(probability_values, default=0),
            "observed_at": current.get("time") or ((hourly.get("time") or [None])[0]),
        }

    @staticmethod
    def weather_label(code: int | None) -> str:
        if code is None:
            return "Dati meteo in attesa"
        labels = {
            0: "Sereno",
            1: "Prevalentemente sereno",
            2: "Parzialmente nuvoloso",
            3: "Coperto",
            45: "Nebbia",
            48: "Nebbia con brina",
            51: "Pioviggine debole",
            53: "Pioviggine",
            55: "Pioviggine intensa",
            61: "Pioggia debole",
            63: "Pioggia",
            65: "Pioggia intensa",
            71: "Neve debole",
            73: "Neve",
            75: "Neve intensa",
            80: "Rovesci deboli",
            81: "Rovesci",
            82: "Rovesci intensi",
            95: "Temporale",
            96: "Temporale con grandine",
            99: "Temporale forte con grandine",
        }
        return labels.get(code, "Condizioni variabili")

    @staticmethod
    def compass_direction(degrees: float | None) -> str | None:
        if degrees is None:
            return None
        points = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
        return points[int((degrees % 360 + 22.5) // 45) % 8]

    async def fetch_dpc_hrd(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Read the current DPC Heavy Rain Detection vector at the GPS point.

        The former ``radar:poh`` WMS layer was removed from the public
        capabilities in Radar-DPC v2. HRD remains queryable and already blends
        precipitation intensity, persistence, convection and hail probability.
        """
        delta = 0.08
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": "radar:hrd",
            "QUERY_LAYERS": "radar:hrd",
            "STYLES": "",
            "SRS": "EPSG:4326",
            "BBOX": (
                f"{longitude-delta},{latitude-delta},"
                f"{longitude+delta},{latitude+delta}"
            ),
            "WIDTH": 101,
            "HEIGHT": 101,
            "X": 50,
            "Y": 50,
            "FEATURE_COUNT": 5,
            "INFO_FORMAT": "application/json",
            "TILED": "true",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://radar-geowebcache.protezionecivile.it/service/wms",
                params=params,
            )
            response.raise_for_status()
            if "json" not in response.headers.get("content-type", "").casefold():
                raise ValueError("Radar-DPC HRD non ha restituito JSON")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Risposta Radar-DPC HRD non valida")
            return payload

    async def fetch_windy(self, latitude: float, longitude: float) -> dict:
        """Fetch Windy Point Forecast when a production API key is configured."""
        body = {
            "lat": latitude,
            "lon": longitude,
            "model": "iconEu" if self._inside_europe(latitude, longitude) else "icon",
            "parameters": ["windGust", "precip", "convPrecip", "cape"],
            "levels": ["surface"],
            "key": self.windy_api_key,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.windy.com/api/point-forecast/v2", json=body
            )
            response.raise_for_status()
            if not response.content:
                raise ValueError("Windy non ha restituito dati")
            return response.json()

    @classmethod
    def analyse_local(cls, states: list[dict[str, Any]]) -> list[WeatherRisk]:
        risks: list[WeatherRisk] = []
        for item in states:
            entity_id = str(item.get("entity_id", "")).casefold()
            name = str(item.get("name", "")).casefold()
            state = str(item.get("state", "")).casefold()
            candidate = f"{entity_id} {name}"
            if "rischio_meteo" in candidate or "rischio meteo" in candidate:
                if "allarme" in state:
                    risks.append(WeatherRisk("temporale", "urgenza", 75, "sensori locali", state))
                elif "attenzione" in state:
                    risks.append(WeatherRisk("temporale", "allerta", 45, "sensori locali", state))
            if any(term in candidate for term in ("grandine", "hail")) and state in {"on", "true", "detected"}:
                risks.append(WeatherRisk("grandine", "urgenza", 85, "sensori locali", "rilevata"))
            if any(term in candidate for term in ("fulmin", "lightning")) and state in {"on", "true", "detected"}:
                risks.append(WeatherRisk("temporale_sviluppato", "urgenza", 80, "sensori locali", "fulmini rilevati"))
        return risks

    @classmethod
    def extract_local_observation(
        cls, states: list[dict[str, Any]]
    ) -> dict[str, float]:
        observation: dict[str, float] = {}
        for item in states:
            candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
            value = cls._number(item.get("state"))
            if value is None:
                continue
            if "temperature" not in observation and (
                ("estern" in candidate or "outdoor" in candidate)
                and any(term in candidate for term in ("temper", "temperature"))
            ):
                observation["temperature"] = value
            if "humidity" not in observation and (
                ("estern" in candidate or "outdoor" in candidate)
                and any(term in candidate for term in ("umid", "humidity"))
            ):
                observation["humidity"] = value
            if "pressure" not in observation and cls._is_barometric_pressure(item):
                observation["pressure"] = value
        return observation

    @staticmethod
    def _is_barometric_pressure(item: dict[str, Any]) -> bool:
        candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
        attributes = item.get("attributes") or {}
        unit = str(
            item.get("unit") or attributes.get("unit_of_measurement") or ""
        ).strip().casefold()
        clearly_atmospheric = any(
            term in candidate
            for term in ("barometr", "atmosfer", "atmospher", "sea_level")
        )
        pressure_named = any(term in candidate for term in ("pression", "pressure"))
        return clearly_atmospheric or (pressure_named and unit in {"hpa", "mbar"})

    def record_local_observation(
        self, observation: dict[str, float]
    ) -> dict[str, Any]:
        if not observation:
            return {}
        now = datetime.now(timezone.utc)
        stored = self.memory.get_json_setting("weather_local_history") or {}
        samples = [item for item in stored.get("samples", []) if isinstance(item, dict)]
        recent = []
        for item in samples:
            observed_at = self._datetime(item.get("observed_at"))
            if observed_at is not None and (now - observed_at).total_seconds() <= 86400:
                recent.append(item)
        reference = None
        for item in recent:
            observed_at = self._datetime(item.get("observed_at"))
            age = (now - observed_at).total_seconds() if observed_at else 0
            if 1500 <= age <= 10800:
                reference = item
                break
        trend: dict[str, Any] = {}
        if reference is not None:
            reference_time = self._datetime(reference.get("observed_at")) or now
            trend["hours"] = round((now - reference_time).total_seconds() / 3600, 2)
            for key in ("pressure", "temperature", "humidity"):
                current_value = self._number(observation.get(key))
                old_value = self._number(reference.get(key))
                if current_value is not None and old_value is not None:
                    trend[f"{key}_delta"] = round(current_value - old_value, 2)
        recent.append({"observed_at": now.isoformat(), **observation})
        self.memory.set_json_setting("weather_local_history", {"samples": recent[-49:]})
        return trend

    @staticmethod
    def analyse_local_trend(trend: dict[str, Any]) -> list[WeatherRisk]:
        pressure_delta = float(trend.get("pressure_delta", 0))
        temperature_delta = float(trend.get("temperature_delta", 0))
        humidity_delta = float(trend.get("humidity_delta", 0))
        hours = float(trend.get("hours", 0))
        if pressure_delta <= -5:
            return [
                WeatherRisk(
                    "pressione_in_calo",
                    "urgenza",
                    73,
                    "barometro locale",
                    f"calo di {abs(pressure_delta):.1f} hPa in {hours:.1f} ore",
                )
            ]
        if pressure_delta <= -2.5:
            severity = (
                "urgenza"
                if humidity_delta >= 10 and temperature_delta <= -2
                else "allerta"
            )
            return [
                WeatherRisk(
                    "pressione_in_calo",
                    severity,
                    68 if severity == "urgenza" else 50,
                    "sensori esterni",
                    (
                        f"pressione {pressure_delta:.1f} hPa, temperatura "
                        f"{temperature_delta:+.1f} °C, umidità {humidity_delta:+.0f}% "
                        f"in {hours:.1f} ore"
                    ),
                )
            ]
        return []

    @classmethod
    def analyse_open_meteo(cls, payload: dict[str, Any]) -> list[WeatherRisk]:
        hourly = payload.get("hourly") or {}
        risks: list[WeatherRisk] = []
        codes = [int(value or 0) for value in (hourly.get("weather_code") or [])[:8]]
        gusts = [cls._number(value) or 0 for value in (hourly.get("wind_gusts_10m") or [])[:8]]
        probability = [cls._number(value) or 0 for value in (hourly.get("precipitation_probability") or [])[:8]]
        showers = [cls._number(value) or 0 for value in (hourly.get("showers") or [])[:8]]
        cape = [cls._number(value) or 0 for value in (hourly.get("cape") or [])[:8]]
        max_gust = max(gusts, default=0)
        max_probability = max(probability, default=0)
        max_showers = max(showers, default=0)
        max_cape = max(cape, default=0)
        if any(code in {96, 99} for code in codes):
            risks.append(WeatherRisk("grandine", "urgenza", 80, "Open-Meteo", "codice temporale con grandine nelle prossime 8 ore"))
        elif 95 in codes:
            risks.append(WeatherRisk("temporale", "urgenza", 68, "Open-Meteo", "temporale previsto nelle prossime 8 ore"))
        if max_gust >= 70:
            risks.append(WeatherRisk("vento", "urgenza", 78, "Open-Meteo", f"raffiche fino a {max_gust:.0f} km/h"))
        elif max_gust >= 50:
            risks.append(WeatherRisk("vento", "allerta", 52, "Open-Meteo", f"raffiche fino a {max_gust:.0f} km/h"))
        if max_probability >= 80 and max_showers >= 8:
            risks.append(WeatherRisk("pioggia_intensa", "allerta", 48, "Open-Meteo", f"probabilità {max_probability:.0f}%, rovesci {max_showers:.1f} mm"))
        if max_cape >= 1500 and not any(r.kind in {"temporale", "grandine"} for r in risks):
            risks.append(WeatherRisk("instabilita", "allerta", 46, "Open-Meteo", f"CAPE fino a {max_cape:.0f} J/kg"))
        return risks

    @classmethod
    def analyse_windy(cls, payload: dict[str, Any]) -> list[WeatherRisk]:
        """Use the first eight forecast samples as an independent comparison."""
        units = payload.get("units") or {}
        gusts = [cls._number(value) or 0 for value in (payload.get("gust-surface") or [])[:8]]
        gust_unit = str(units.get("gust-surface", "")).casefold()
        if "m*s-1" in gust_unit or "m/s" in gust_unit:
            gusts = [value * 3.6 for value in gusts]
        convective = [
            cls._number(value) or 0
            for value in (payload.get("past3hconvprecip-surface") or [])[:8]
        ]
        cape = [cls._number(value) or 0 for value in (payload.get("cape-surface") or [])[:8]]
        risks: list[WeatherRisk] = []
        max_gust = max(gusts, default=0)
        max_convective = max(convective, default=0)
        max_cape = max(cape, default=0)
        if max_gust >= 70:
            risks.append(WeatherRisk("vento", "urgenza", 80, "Windy", f"raffiche fino a {max_gust:.0f} km/h"))
        elif max_gust >= 50:
            risks.append(WeatherRisk("vento", "allerta", 54, "Windy", f"raffiche fino a {max_gust:.0f} km/h"))
        if max_cape >= 1500 and max_convective >= 3:
            risks.append(
                WeatherRisk(
                    "temporale",
                    "urgenza" if max_cape >= 2500 or max_convective >= 8 else "allerta",
                    72 if max_cape >= 2500 or max_convective >= 8 else 50,
                    "Windy",
                    f"convezione {max_convective:.1f} mm/3h, CAPE {max_cape:.0f} J/kg",
                )
            )
        return risks

    @staticmethod
    def analyse_dpc_hail(probability: float) -> list[WeatherRisk]:
        if probability >= 70:
            return [WeatherRisk("grandine", "emergenza", 95, "Radar-DPC", f"probabilità puntuale {probability:.0f}%")]
        if probability >= 40:
            return [WeatherRisk("grandine", "urgenza", 84, "Radar-DPC", f"probabilità puntuale {probability:.0f}%")]
        if probability >= 20:
            return [WeatherRisk("grandine", "allerta", 55, "Radar-DPC", f"probabilità puntuale {probability:.0f}%")]
        return []

    @classmethod
    def analyse_dpc_hrd(cls, payload: dict[str, Any]) -> list[WeatherRisk]:
        """Translate current HRD features into conservative local risks."""
        features = payload.get("features") or []
        if not isinstance(features, list) or not features:
            return []

        probability = cls._find_hail_probability(features)
        if probability is not None:
            hail_risks = cls.analyse_dpc_hail(probability)
            if hail_risks:
                return hail_risks

        severity_value: float | None = None
        severity_text = ""
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties") or {}
            if not isinstance(properties, dict):
                continue
            for key, value in properties.items():
                normalized = str(key).casefold()
                if any(term in normalized for term in ("severity", "severita", "indice", "index")):
                    number = cls._number(value)
                    if number is not None:
                        severity_value = max(severity_value or number, number)
                    elif value is not None:
                        severity_text = f"{severity_text} {value}".strip().casefold()

        urgent_words = ("high", "severe", "extreme", "alto", "elevato", "rosso")
        warning_words = ("medium", "moderate", "medio", "arancio", "giallo")
        if (severity_value is not None and severity_value >= 3) or any(
            word in severity_text for word in urgent_words
        ):
            return [
                WeatherRisk(
                    "temporale_sviluppato",
                    "urgenza",
                    82,
                    "Radar-DPC HRD",
                    "area temporalesca intensa rilevata sulla posizione",
                )
            ]
        if (severity_value is not None and severity_value >= 1) or any(
            word in severity_text for word in warning_words
        ):
            return [
                WeatherRisk(
                    "temporale",
                    "allerta",
                    58,
                    "Radar-DPC HRD",
                    "fenomeno convettivo rilevato sulla posizione",
                )
            ]
        return [
            WeatherRisk(
                "pioggia_intensa",
                "allerta",
                50,
                "Radar-DPC HRD",
                "area HRD rilevata sulla posizione",
            )
        ]

    @staticmethod
    def assess(risks: list[WeatherRisk]) -> dict[str, Any]:
        if not risks:
            return {"severity": "nessuna", "score": 0, "kinds": [], "risks": []}
        severity = max(risks, key=lambda item: SEVERITY_RANK[item.severity]).severity
        score = max(item.score for item in risks)
        return {
            "severity": severity,
            "score": score,
            "kinds": sorted({item.kind for item in risks}),
            "risks": [asdict(item) for item in risks],
        }

    def should_notify(self, current: dict[str, Any]) -> tuple[bool, str]:
        previous = self.memory.get_json_setting("weather_monitor_state") or {}
        current_rank = SEVERITY_RANK.get(str(current.get("severity")), 0)
        previous_rank = SEVERITY_RANK.get(str(previous.get("severity")), 0)
        if current_rank == 0:
            return False, "nessun rischio"
        if previous_rank == 0:
            return True, "nuovo rischio"
        if current_rank > previous_rank:
            return True, "previsioni peggiorate"
        new_kinds = set(current.get("kinds") or []) - set(previous.get("kinds") or [])
        if new_kinds & {"grandine", "temporale", "temporale_sviluppato"}:
            return True, "nuovo temporale o rischio grandine"
        if int(current.get("score") or 0) >= int(previous.get("score") or 0) + 20:
            return True, "intensità aumentata sensibilmente"
        return False, "evento già notificato e non peggiorato"

    async def _notify(self, assessment: dict[str, Any]) -> None:
        severity = str(assessment["severity"])
        title = f"Mistermif AI · Meteo {severity.upper()}"
        risks = assessment.get("risks") or []
        summary = "; ".join(
            f'{risk["kind"]}: {risk["detail"]} ({risk["source"]})'
            for risk in risks[:5]
        )
        ai_summary = str(
            (assessment.get("gemini_review") or {}).get("summary") or ""
        ).strip()
        if ai_summary:
            summary = f"{summary}. Valutazione Gemini: {ai_summary}" if summary else ai_summary
        movement = " Caravan in movimento." if assessment.get("moving") else ""
        message = f"{summary}.{movement}" if summary else f"Rischio meteo {severity}.{movement}"
        try:
            await self.ha.send_notification(self.notification_service, title, message)
        except (httpx.HTTPError, RuntimeError, PermissionError, ValueError):
            logger.exception("Notifica Home Assistant non riuscita")
        if SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK["urgenza"]:
            try:
                await self.ha.send_telegram(
                    self.telegram_targets,
                    f"⚠️ {title}\n{message}",
                )
            except (httpx.HTTPError, RuntimeError, PermissionError, ValueError):
                logger.exception("Notifica Telegram non riuscita")

    @classmethod
    def _location(cls, states: list[dict[str, Any]]) -> tuple[float, float] | None:
        lat = lon = None
        for item in states:
            candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
            if "gps" in candidate and ("latitude" in candidate or "latitudine" in candidate):
                lat = cls._number(item.get("state"))
            if "gps" in candidate and ("longitude" in candidate or "longitudine" in candidate):
                lon = cls._number(item.get("state"))
        if lat is not None and lon is not None and (lat != 0 or lon != 0):
            return lat, lon
        for item in states:
            if str(item.get("entity_id", "")).startswith("device_tracker.caravan"):
                attrs = item.get("attributes") or {}
                lat = cls._number(attrs.get("latitude"))
                lon = cls._number(attrs.get("longitude"))
                if lat is not None and lon is not None and (lat != 0 or lon != 0):
                    return lat, lon
        return None

    @classmethod
    def _movement(cls, states: list[dict[str, Any]]) -> bool:
        for item in states:
            candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
            if "gps" in candidate and ("veloc" in candidate or "speed" in candidate):
                return (cls._number(item.get("state")) or 0) > 5
        return False

    @classmethod
    def _find_probability(cls, value: Any, key: str = "") -> float | None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                result = cls._find_probability(child, str(child_key).casefold())
                if result is not None:
                    return result
        elif isinstance(value, list):
            for child in value:
                result = cls._find_probability(child, key)
                if result is not None:
                    return result
        elif any(term in key for term in ("poh", "prob", "value", "gray_index")):
            number = cls._number(value)
            if number is not None and 0 <= number <= 100:
                return number
        return None

    @classmethod
    def _find_hail_probability(cls, value: Any, key: str = "") -> float | None:
        """Find only explicitly hail-related percentages in an HRD feature."""
        if isinstance(value, dict):
            for child_key, child in value.items():
                result = cls._find_hail_probability(
                    child, str(child_key).casefold()
                )
                if result is not None:
                    return result
        elif isinstance(value, list):
            for child in value:
                result = cls._find_hail_probability(child, key)
                if result is not None:
                    return result
        elif any(term in key for term in ("poh", "hail", "grandine")):
            number = cls._number(value)
            if number is not None and 0 <= number <= 100:
                return number
        return None

    @staticmethod
    def _inside_italy(latitude: float, longitude: float) -> bool:
        return 35.0 <= latitude <= 48.0 and 4.0 <= longitude <= 20.5

    @staticmethod
    def _inside_europe(latitude: float, longitude: float) -> bool:
        return 27.0 <= latitude <= 72.0 and -25.0 <= longitude <= 45.0

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None
