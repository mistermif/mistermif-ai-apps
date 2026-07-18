from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    model: str = "gpt-5.4-mini"
    autonomy_mode: str = "observe"
    climate_entity: str = "climate.thermal_control"
    notification_service: str = "notify.notify"
    privacy_mode: str = "local_only"
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

        api_key = str(options.get("openai_api_key") or os.getenv("OPENAI_API_KEY", ""))
        mode = str(options.get("autonomy_mode", "observe"))
        if mode not in {"observe", "confirm", "limited"}:
            mode = "observe"
        privacy_mode = str(options.get("privacy_mode", "local_only"))
        if privacy_mode not in {"local_only", "redacted_cloud"}:
            privacy_mode = "local_only"

        try:
            max_context_entities = int(options.get("max_context_entities", 80))
        except (TypeError, ValueError):
            max_context_entities = 80
        max_context_entities = min(200, max(10, max_context_entities))

        return cls(
            openai_api_key=api_key,
            model=str(options.get("model", "gpt-5.4-mini")),
            autonomy_mode=mode,
            climate_entity=str(
                options.get("climate_entity", "climate.thermal_control")
            ),
            notification_service=str(
                options.get("notification_service", "notify.notify")
            ),
            privacy_mode=privacy_mode,
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
