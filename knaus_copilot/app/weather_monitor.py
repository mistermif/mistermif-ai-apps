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
    """Deterministic weather supervisor. No LLM or cloud token is used."""

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
            try:
                forecast = await self.fetch_open_meteo(latitude, longitude)
                risks.extend(self.analyse_open_meteo(forecast))
                sources["open_meteo_multimodello"] = "ok"
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                logger.exception("Open-Meteo non disponibile")
                sources["open_meteo_multimodello"] = "errore"
            if self.dpc_enabled and self._inside_italy(latitude, longitude):
                try:
                    poh = await self.fetch_dpc_hail_probability(latitude, longitude)
                    sources["radar_dpc_grandine"] = (
                        "dato disponibile" if poh is not None else "nessun valore puntuale"
                    )
                    if poh is not None:
                        risks.extend(self.analyse_dpc_hail(poh))
                except (httpx.HTTPError, ValueError, TypeError):
                    logger.exception("Radar-DPC non disponibile")
                    sources["radar_dpc_grandine"] = "errore"
            else:
                sources["radar_dpc_grandine"] = "fuori Italia o disattivato"
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
                ai_review = await self.ai_evaluator(
                    deterministic,
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
            "hourly": (
                "weather_code,precipitation_probability,precipitation,rain,"
                "showers,wind_gusts_10m,cape,temperature_2m"
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

    async def fetch_dpc_hail_probability(
        self, latitude: float, longitude: float
    ) -> float | None:
        delta = 0.08
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": "radar:poh",
            "QUERY_LAYERS": "radar:poh",
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
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://radar-geowebcache.protezionecivile.it/service/wms",
                params=params,
            )
            response.raise_for_status()
            if "json" not in response.headers.get("content-type", "").casefold():
                return None
            return self._find_probability(response.json())

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
            if any(term in candidate for term in ("pression", "baro", "pressure")):
                value = cls._number(item.get("state"))
                if value is not None and value < 950:
                    risks.append(WeatherRisk("pressione", "urgenza", 70, "barometro locale", f"{value:.0f} hPa"))
                elif value is not None and value < 970:
                    risks.append(WeatherRisk("pressione", "allerta", 35, "barometro locale", f"{value:.0f} hPa"))
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
            if "pressure" not in observation and any(
                term in candidate for term in ("pression", "pressure", "barometr")
            ):
                observation["pressure"] = value
        return observation

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
