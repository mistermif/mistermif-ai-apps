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
