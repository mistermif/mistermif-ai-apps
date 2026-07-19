from __future__ import annotations

import threading
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .memory import MemoryStore


class CloudBudgetExceeded(RuntimeError):
    pass


class CloudUsage:
    """Persistent daily limiter. Automatic calls cannot consume the manual reserve."""

    def __init__(
        self,
        memory: MemoryStore,
        daily_limit: int,
        automatic_limit: int,
        timezone_name: str = "Europe/Rome",
    ):
        self.memory = memory
        self.daily_limit = daily_limit
        self.automatic_limit = automatic_limit
        self.timezone = ZoneInfo(timezone_name)
        self._lock = threading.Lock()

    def _today(self) -> str:
        return datetime.now(self.timezone).date().isoformat()

    def snapshot(self) -> dict[str, Any]:
        value = self.memory.get_json_setting("cloud_usage") or {}
        if value.get("date") != self._today():
            value = {"date": self._today(), "total": 0, "automatic": 0}
        total = int(value.get("total", 0))
        automatic = int(value.get("automatic", 0))
        return {
            "date": value["date"],
            "total": total,
            "automatic": automatic,
            "daily_limit": self.daily_limit,
            "automatic_limit": self.automatic_limit,
            "remaining": max(0, self.daily_limit - total),
            "automatic_remaining": max(0, self.automatic_limit - automatic),
        }

    def consume(self, automatic: bool = False) -> dict[str, Any]:
        with self._lock:
            usage = self.snapshot()
            if usage["total"] >= self.daily_limit:
                raise CloudBudgetExceeded(
                    "Budget cloud giornaliero esaurito; il controllo locale continua."
                )
            if automatic and usage["automatic"] >= self.automatic_limit:
                raise CloudBudgetExceeded(
                    "Budget delle ricerche automatiche esaurito; "
                    "le richieste manuali restano disponibili."
                )
            payload = {
                "date": usage["date"],
                "total": usage["total"] + 1,
                "automatic": usage["automatic"] + (1 if automatic else 0),
            }
            self.memory.set_json_setting("cloud_usage", payload)
            return self.snapshot()
