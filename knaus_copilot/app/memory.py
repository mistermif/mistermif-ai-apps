from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, database_path: Path):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._lock = threading.Lock()
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_database(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_user
                    ON messages(user_id, id DESC);

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_owner
                    ON memories(owner_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS runtime_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_key TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_site_time
                    ON learning_observations(site_key, observed_at DESC);

                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_key TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    outcome TEXT,
                    score REAL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );

                CREATE TABLE IF NOT EXISTS travel_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    destination TEXT NOT NULL,
                    departure_text TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'planned',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_travel_plans_status
                    ON travel_plans(status, id DESC);

                CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER,
                    destination TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    start_lat REAL,
                    start_lon REAL,
                    end_lat REAL,
                    end_lon REAL,
                    distance_km REAL NOT NULL DEFAULT 0,
                    moving_seconds REAL NOT NULL DEFAULT 0,
                    max_speed_kmh REAL NOT NULL DEFAULT 0,
                    stop_count INTEGER NOT NULL DEFAULT 0,
                    stationary_since TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_trips_status
                    ON trips(status, id DESC);

                CREATE TABLE IF NOT EXISTS trip_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    speed_kmh REAL NOT NULL DEFAULT 0,
                    temperature REAL,
                    humidity REAL,
                    pressure REAL,
                    weather_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_trip_points_trip
                    ON trip_points(trip_id, id);
                """
            )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM runtime_settings WHERE key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO runtime_settings(key, value, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def get_json_setting(self, key: str) -> dict[str, Any] | None:
        value = self.get_setting(key)
        if not value:
            return None
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None

    def set_json_setting(self, key: str, value: dict[str, Any]) -> None:
        self.set_setting(key, json.dumps(value, ensure_ascii=False))

    def add_learning_observation(
        self,
        site_key: str,
        payload: dict[str, Any],
        observed_at: str | None = None,
    ) -> int:
        timestamp = observed_at or datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO learning_observations(site_key, observed_at, payload_json)
                VALUES(?,?,?)
                """,
                (site_key, timestamp, json.dumps(payload, ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    def recent_learning_observations(
        self,
        site_key: str,
        limit: int = 288,
    ) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT observed_at, payload_json
                FROM learning_observations
                WHERE site_key = ?
                ORDER BY id DESC LIMIT ?
                """,
                (site_key, limit),
            ).fetchall()
        return [
            {
                "observed_at": row["observed_at"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in reversed(rows)
        ]

    def learning_site_count(self) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(DISTINCT site_key) AS total FROM learning_observations"
            ).fetchone()
        return int(row["total"] if row else 0)

    def add_decision(
        self,
        site_key: str,
        decision: str,
        context: dict[str, Any],
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO decision_outcomes(
                    site_key, decision, context_json, created_at
                ) VALUES(?,?,?,?)
                """,
                (site_key, decision, json.dumps(context, ensure_ascii=False), now),
            )
            return int(cursor.lastrowid)

    def resolve_decision(self, decision_id: int, outcome: str, score: float) -> None:
        score = max(-1.0, min(1.0, float(score)))
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute(
                """
                UPDATE decision_outcomes
                SET outcome = ?, score = ?, resolved_at = ?
                WHERE id = ?
                """,
                (outcome, score, now, decision_id),
            )

    def add_message(self, user_id: str, role: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO messages(user_id, role, content, created_at) VALUES(?,?,?,?)",
                (user_id, role, content, now),
            )

    def recent_messages(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT role, content, created_at
                FROM messages WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_memory(
        self,
        owner_id: str,
        category: str,
        title: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO memories(
                    owner_id, category, title, content, metadata_json,
                    created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    owner_id,
                    category,
                    title,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_memories(self, owner_id: str, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT id, owner_id, category, title, content, metadata_json,
                       created_at, updated_at
                FROM memories
                WHERE owner_id IN (?, 'shared')
                ORDER BY updated_at DESC LIMIT ?
                """,
                (owner_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            result.append(item)
        return result

    def add_travel_plan(self, destination: str, departure_text: str = "") -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO travel_plans(destination, departure_text, created_at)
                VALUES(?,?,?)
                """,
                (destination.strip(), departure_text.strip(), now),
            )
            return int(cursor.lastrowid)

    def pending_travel_plan(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT * FROM travel_plans
                WHERE status = 'planned'
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def start_trip(
        self,
        latitude: float,
        longitude: float,
        destination: str = "",
        plan_id: int | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO trips(
                    plan_id, destination, started_at, start_lat, start_lon
                ) VALUES(?,?,?,?,?)
                """,
                (plan_id, destination, now, latitude, longitude),
            )
            trip_id = int(cursor.lastrowid)
            if plan_id is not None:
                db.execute(
                    """
                    UPDATE travel_plans
                    SET status = 'started', started_at = ? WHERE id = ?
                    """,
                    (now, plan_id),
                )
            return trip_id

    def active_trip(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM trips WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def add_trip_point(
        self,
        trip_id: int,
        observed_at: str,
        latitude: float,
        longitude: float,
        speed_kmh: float,
        temperature: float | None = None,
        humidity: float | None = None,
        pressure: float | None = None,
        weather: dict[str, Any] | None = None,
    ) -> int:
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO trip_points(
                    trip_id, observed_at, latitude, longitude, speed_kmh,
                    temperature, humidity, pressure, weather_json
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    trip_id,
                    observed_at,
                    latitude,
                    longitude,
                    speed_kmh,
                    temperature,
                    humidity,
                    pressure,
                    json.dumps(weather or {}, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def update_trip_progress(
        self,
        trip_id: int,
        *,
        distance_km: float,
        moving_seconds: float,
        max_speed_kmh: float,
        stop_count: int,
        stationary_since: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                UPDATE trips SET
                    distance_km = ?, moving_seconds = ?, max_speed_kmh = ?,
                    stop_count = ?, stationary_since = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    distance_km,
                    moving_seconds,
                    max_speed_kmh,
                    stop_count,
                    stationary_since,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    trip_id,
                ),
            )

    def finish_trip(
        self,
        trip_id: int,
        latitude: float,
        longitude: float,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT plan_id FROM trips WHERE id = ?", (trip_id,)
            ).fetchone()
            db.execute(
                """
                UPDATE trips SET status = 'completed', ended_at = ?,
                    end_lat = ?, end_lon = ? WHERE id = ?
                """,
                (now, latitude, longitude, trip_id),
            )
            if row and row["plan_id"] is not None:
                db.execute(
                    """
                    UPDATE travel_plans
                    SET status = 'completed', completed_at = ? WHERE id = ?
                    """,
                    (now, row["plan_id"]),
                )

    def list_trips(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM trips ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            result.append(item)
        return result

    def trip_detail(self, trip_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            trip = db.execute(
                "SELECT * FROM trips WHERE id = ?", (trip_id,)
            ).fetchone()
            points = db.execute(
                "SELECT * FROM trip_points WHERE trip_id = ? ORDER BY id",
                (trip_id,),
            ).fetchall()
        if not trip:
            return None
        result = dict(trip)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        result["points"] = []
        for row in points:
            point = dict(row)
            point["weather"] = json.loads(point.pop("weather_json"))
            result["points"].append(point)
        return result
