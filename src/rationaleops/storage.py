"""SQLite persistence for local workflow state and audit events."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class WorkflowStore:
    """Persist one or more demo sessions without hiding state in process memory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_sessions (
                    id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES workflow_sessions(id)
                );
                """
            )

    def load(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM workflow_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return json.loads(row["snapshot_json"]) if row else None

    def save(self, session_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            current = connection.execute(
                "SELECT version FROM workflow_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            version = int(current["version"]) + 1 if current else 1
            snapshot["version"] = version
            snapshot["updated_at"] = now
            payload = json.dumps(snapshot, separators=(",", ":"))
            connection.execute(
                """
                INSERT INTO workflow_sessions(id, version, snapshot_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                """,
                (session_id, version, payload, now),
            )
        return snapshot

    def append_event(
        self,
        session_id: str,
        *,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_events(
                    session_id, event_type, actor, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event_type,
                    actor,
                    json.dumps(payload, separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def events(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_type, actor, payload_json, created_at
                FROM workflow_events
                WHERE session_id = ?
                ORDER BY sequence
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def reset(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM workflow_events WHERE session_id = ?",
                (session_id,),
            )
            connection.execute(
                "DELETE FROM workflow_sessions WHERE id = ?",
                (session_id,),
            )
