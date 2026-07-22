from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    ai_provider: str = "local"
    ai_api_key: str = ""
    ai_base_url: str = ""
    model: str = "gpt-5.4-mini"
    autonomy_mode: str = "observe"
    climate_entity: str = "climate.thermal_control"
    notification_service: str = "notify.notify"
    privacy_mode: str = "local_only"
    cloud_daily_limit: int = 15
    cloud_automatic_limit: int = 5
    gemini_search_enabled: bool = False
    workspace_enabled: bool = True
    homeassistant_config_dir: Path = Path("/homeassistant")
    max_context_entities: int = 80
    log_level: str = "info"
    data_dir: Path = Path("/data")
    supervisor_token: str = ""
    ha_base_url: str = "http://supervisor/core/api"
    codex_bridge_enabled: bool = False
    codex_bridge_token: str = ""
    codex_bridge_port: int = 8100
    weather_monitor_enabled: bool = True
    weather_interval_minutes: int = 30
    dpc_radar_enabled: bool = True
    windy_api_key: str = ""
    telegram_targets: tuple[str, ...] = ()
    weather_ai_enabled: bool = True
    weather_ai_daily_limit: int = 10
    travel_tracker_enabled: bool = True
    travel_poll_seconds: int = 30
    travel_arrival_minutes: int = 120

    @classmethod
    def load(cls) -> "Settings":
        data_dir = Path(os.getenv("KNAUS_DATA_DIR", "/data"))
        options_path = Path(
            os.getenv("KNAUS_OPTIONS_FILE", str(data_dir / "options.json"))
        )
        options: dict = {}
        if options_path.exists():
            options = json.loads(options_path.read_text(encoding="utf-8"))

        legacy_openai_key = str(
            options.get("openai_api_key") or os.getenv("OPENAI_API_KEY", "")
        )
        ai_provider = str(options.get("ai_provider", "openai" if legacy_openai_key else "local"))
        if ai_provider not in {"local", "openai", "groq", "gemini"}:
            ai_provider = "local"
        ai_api_key = str(
            options.get("ai_api_key")
            or (legacy_openai_key if ai_provider == "openai" else "")
            or os.getenv("AI_API_KEY", "")
        )
        default_base_urls = {
            "local": "",
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
        }
        ai_base_url = str(
            options.get("ai_base_url") or default_base_urls[ai_provider]
        ).rstrip("/")
        mode = str(options.get("autonomy_mode", "observe"))
        if mode not in {"observe", "confirm", "limited"}:
            mode = "observe"
        privacy_mode = str(options.get("privacy_mode", "local_only"))
        if privacy_mode not in {
            "local_only",
            "redacted_cloud",
            "contextual_cloud",
        }:
            privacy_mode = "local_only"

        try:
            max_context_entities = int(options.get("max_context_entities", 80))
        except (TypeError, ValueError):
            max_context_entities = 80
        max_context_entities = min(200, max(10, max_context_entities))
        try:
            cloud_daily_limit = int(options.get("cloud_daily_limit", 15))
        except (TypeError, ValueError):
            cloud_daily_limit = 15
        cloud_daily_limit = min(490, max(1, cloud_daily_limit))
        try:
            cloud_automatic_limit = int(options.get("cloud_automatic_limit", 5))
        except (TypeError, ValueError):
            cloud_automatic_limit = 5
        cloud_automatic_limit = min(
            cloud_daily_limit, max(0, cloud_automatic_limit)
        )
        try:
            weather_interval_minutes = int(
                options.get("weather_interval_minutes", 30)
            )
        except (TypeError, ValueError):
            weather_interval_minutes = 30
        weather_interval_minutes = min(180, max(15, weather_interval_minutes))
        try:
            weather_ai_daily_limit = int(
                options.get("weather_ai_daily_limit", 10)
            )
        except (TypeError, ValueError):
            weather_ai_daily_limit = 10
        weather_ai_daily_limit = min(10, max(0, weather_ai_daily_limit))
        try:
            travel_poll_seconds = int(options.get("travel_poll_seconds", 30))
        except (TypeError, ValueError):
            travel_poll_seconds = 30
        travel_poll_seconds = min(300, max(15, travel_poll_seconds))
        try:
            travel_arrival_minutes = int(
                options.get("travel_arrival_minutes", 120)
            )
        except (TypeError, ValueError):
            travel_arrival_minutes = 120
        travel_arrival_minutes = min(360, max(15, travel_arrival_minutes))
        raw_targets = options.get("telegram_targets", "")
        if isinstance(raw_targets, list):
            telegram_targets = tuple(
                str(item).strip() for item in raw_targets if str(item).strip()
            )
        else:
            telegram_targets = tuple(
                item.strip() for item in str(raw_targets).split(",") if item.strip()
            )

        model = str(options.get("model", "gpt-5.4-mini"))
        if ai_provider == "groq" and (
            not options.get("model")
            or model.startswith("gpt-5.")
            or model == "local-rules"
        ):
            model = "openai/gpt-oss-20b"
        if ai_provider == "local" and not options.get("model"):
            model = "local-rules"
        if ai_provider == "gemini" and (
            not options.get("model")
            or model.startswith("gpt-")
            or model in {"local-rules", "openai/gpt-oss-20b"}
        ):
            model = "gemini-3.5-flash"

        return cls(
            openai_api_key=legacy_openai_key,
            ai_provider=ai_provider,
            ai_api_key=ai_api_key,
            ai_base_url=ai_base_url,
            model=model,
            autonomy_mode=mode,
            climate_entity=str(
                options.get("climate_entity", "climate.thermal_control")
            ),
            notification_service=str(
                options.get("notification_service", "notify.notify")
            ),
            privacy_mode=privacy_mode,
            cloud_daily_limit=cloud_daily_limit,
            cloud_automatic_limit=cloud_automatic_limit,
            gemini_search_enabled=bool(
                options.get("gemini_search_enabled", True)
            ),
            workspace_enabled=bool(options.get("workspace_enabled", True)),
            max_context_entities=max_context_entities,
            log_level=str(options.get("log_level", "info")),
            data_dir=data_dir,
            homeassistant_config_dir=Path(
                os.getenv("HOME_ASSISTANT_CONFIG_DIR", "/homeassistant")
            ),
            supervisor_token=os.getenv("SUPERVISOR_TOKEN", ""),
            ha_base_url=os.getenv(
                "HOME_ASSISTANT_API_URL", "http://supervisor/core/api"
            ).rstrip("/"),
            codex_bridge_enabled=bool(
                options.get("codex_bridge_enabled", False)
            ),
            codex_bridge_token=str(
                options.get("codex_bridge_token")
                or os.getenv("MISTERMIF_BRIDGE_TOKEN", "")
            ),
            codex_bridge_port=int(
                os.getenv("MISTERMIF_BRIDGE_PORT", "8100")
            ),
            weather_monitor_enabled=bool(
                options.get("weather_monitor_enabled", True)
            ),
            weather_interval_minutes=weather_interval_minutes,
            dpc_radar_enabled=bool(options.get("dpc_radar_enabled", True)),
            windy_api_key=str(options.get("windy_api_key", "")),
            telegram_targets=telegram_targets,
            weather_ai_enabled=bool(options.get("weather_ai_enabled", True)),
            weather_ai_daily_limit=weather_ai_daily_limit,
            travel_tracker_enabled=bool(
                options.get("travel_tracker_enabled", True)
            ),
            travel_poll_seconds=travel_poll_seconds,
            travel_arrival_minutes=travel_arrival_minutes,
        )
