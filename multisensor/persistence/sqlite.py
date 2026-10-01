"""Repositorios SQLite durables para el dominio derivado multisensor."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from multisensor.contracts import Incident, Location, Situation

from .repositories import RepositoryError

T = TypeVar("T", Situation, Incident)


class SQLiteDomainRepository:
    """Almacena situaciones e incidentes sin acoplar motores a SQLite."""

    def __init__(self, path: str | Path = "data/multisensor.sqlite3") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS situations (
                id TEXT PRIMARY KEY,
                situation_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                confidence REAL NOT NULL,
                observation_ids TEXT NOT NULL,
                evidence_ids TEXT NOT NULL,
                location TEXT,
                status TEXT NOT NULL,
                explanation TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                incident_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                evidence_ids TEXT NOT NULL,
                confidence REAL NOT NULL,
                location TEXT,
                status TEXT NOT NULL,
                explanation TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def save_situation(self, situation: Situation) -> Situation:
        if self.get_situation(situation.id) is not None:
            raise RepositoryError(f"situación duplicada: {situation.id}")
        self.connection.execute(
            "INSERT INTO situations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                situation.id,
                situation.situation_type,
                situation.started_at.isoformat(),
                situation.updated_at.isoformat(),
                situation.confidence,
                json.dumps(situation.observation_ids),
                json.dumps(situation.evidence_ids),
                json.dumps(situation.location.to_dict()) if situation.location else None,
                situation.status,
                situation.explanation,
                json.dumps(dict(situation.payload), sort_keys=True),
            ),
        )
        self.connection.commit()
        return situation

    def get_situation(self, situation_id: str) -> Situation | None:
        row = self.connection.execute("SELECT * FROM situations WHERE id = ?", (situation_id,)).fetchone()
        return self._situation_from_row(row) if row else None

    def all_situations(self) -> tuple[Situation, ...]:
        rows = self.connection.execute("SELECT * FROM situations ORDER BY started_at, id").fetchall()
        return tuple(self._situation_from_row(row) for row in rows)

    def save_incident(self, incident: Incident) -> Incident:
        if self.get_incident(incident.id) is not None:
            raise RepositoryError(f"incidente duplicado: {incident.id}")
        self.connection.execute(
            "INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                incident.id,
                incident.incident_type,
                incident.started_at.isoformat(),
                incident.updated_at.isoformat(),
                json.dumps(incident.evidence_ids),
                incident.confidence,
                json.dumps(incident.location.to_dict()) if incident.location else None,
                incident.status,
                incident.explanation,
                json.dumps(dict(incident.payload), sort_keys=True),
            ),
        )
        self.connection.commit()
        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        row = self.connection.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return self._incident_from_row(row) if row else None

    def all_incidents(self) -> tuple[Incident, ...]:
        rows = self.connection.execute("SELECT * FROM incidents ORDER BY started_at, id").fetchall()
        return tuple(self._incident_from_row(row) for row in rows)

    @staticmethod
    def _location(value: str | None) -> Location | None:
        if value is None:
            return None
        data = json.loads(value)
        return Location(latitude=data["latitude"], longitude=data["longitude"])

    @classmethod
    def _situation_from_row(cls, row: sqlite3.Row) -> Situation:
        return Situation(
            id=row["id"],
            situation_type=row["situation_type"],
            started_at=datetime.fromisoformat(row["started_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            confidence=row["confidence"],
            observation_ids=tuple(json.loads(row["observation_ids"])),
            evidence_ids=tuple(json.loads(row["evidence_ids"])),
            location=cls._location(row["location"]),
            status=row["status"],
            explanation=row["explanation"],
            payload=json.loads(row["payload"]),
        )

    @classmethod
    def _incident_from_row(cls, row: sqlite3.Row) -> Incident:
        return Incident(
            id=row["id"],
            incident_type=row["incident_type"],
            started_at=datetime.fromisoformat(row["started_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            evidence_ids=tuple(json.loads(row["evidence_ids"])),
            confidence=row["confidence"],
            location=cls._location(row["location"]),
            status=row["status"],
            explanation=row["explanation"],
            payload=json.loads(row["payload"]),
        )

    def close(self) -> None:
        self.connection.close()
