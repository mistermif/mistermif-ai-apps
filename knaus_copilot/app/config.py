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
    cloud_daily_limit: int = 450
    cloud_automatic_limit: int = 60
    gemini_search_enabled: bool = True
    workspace_enabled: bool = True
    homeassistant_config_dir: Path = Path("/homeassistant")
    max_context_entities: int = 80
    log_level: str = "info"
    data_dir: Path = Path("/data")
    supervisor_token: str = ""
    ha_base_url: str = "http://supervisor/core/api"

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
            cloud_daily_limit = int(options.get("cloud_daily_limit", 450))
        except (TypeError, ValueError):
            cloud_daily_limit = 450
        cloud_daily_limit = min(490, max(1, cloud_daily_limit))
        try:
            cloud_automatic_limit = int(options.get("cloud_automatic_limit", 60))
        except (TypeError, ValueError):
            cloud_automatic_limit = 60
        cloud_automatic_limit = min(
            cloud_daily_limit, max(0, cloud_automatic_limit)
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
            model = "gemini-2.5-flash"

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
        )
