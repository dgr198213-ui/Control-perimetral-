"""Cola durable y agnóstica de acciones de protección."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class ActionRequest:
    id: str
    action_type: str
    subject_id: str
    payload: dict[str, object]
    created_at: datetime
    status: str = "pending"
    attempts: int = 0
    available_at: datetime | None = None


class ActionQueue:
    """Persiste acciones y permite reclamarlas con reintentos controlados."""

    def __init__(self, path: str | Path = "data/actions.sqlite3", *, max_attempts: int = 5) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts debe ser positivo")
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.max_attempts = max_attempts
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                available_at TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def enqueue(self, request: ActionRequest) -> bool:
        """Inserta una acción una sola vez; devuelve False si ya existe."""
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO actions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request.id,
                request.action_type,
                request.subject_id,
                _json(request.payload),
                request.created_at.astimezone(timezone.utc).isoformat(),
                request.status,
                request.attempts,
                (request.available_at or request.created_at).astimezone(timezone.utc).isoformat(),
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def process(self, sender: Callable[[ActionRequest], None], *, now: datetime | None = None) -> int:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        rows = self.connection.execute(
            "SELECT * FROM actions WHERE status = 'pending' AND available_at <= ? ORDER BY created_at, id",
            (current.isoformat(),),
        ).fetchall()
        processed = 0
        for row in rows:
            request = self._from_row(row)
            try:
                sender(request)
            except Exception:
                attempts = request.attempts + 1
                if attempts >= self.max_attempts:
                    self.connection.execute(
                        "UPDATE actions SET status='dead_letter', attempts=? WHERE id=?",
                        (attempts, request.id),
                    )
                else:
                    delay = 2 ** attempts
                    self.connection.execute(
                        "UPDATE actions SET attempts=?, available_at=? WHERE id=?",
                        (attempts, (current + timedelta(seconds=delay)).isoformat(), request.id),
                    )
            else:
                self.connection.execute("UPDATE actions SET status='sent', attempts=? WHERE id=?", (request.attempts + 1, request.id))
            processed += 1
        self.connection.commit()
        return processed

    def get_status(self, action_id: str) -> str | None:
        row = self.connection.execute("SELECT status FROM actions WHERE id = ?", (action_id,)).fetchone()
        return row["status"] if row else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ActionRequest:
        return ActionRequest(
            id=row["id"],
            action_type=row["action_type"],
            subject_id=row["subject_id"],
            payload=_from_json(row["payload"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
            attempts=row["attempts"],
            available_at=datetime.fromisoformat(row["available_at"]),
        )

    def close(self) -> None:
        self.connection.close()


def _json(value: dict[str, object]) -> str:
    import json

    return json.dumps(value, sort_keys=True)


def _from_json(value: str) -> dict[str, object]:
    import json

    return json.loads(value)
