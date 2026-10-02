"""Pruebas de persistencia SQLite del dominio derivado."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from multisensor.contracts import Incident, Situation
from multisensor.persistence import RepositoryError, SQLiteDomainRepository


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def test_sqlite_repository_round_trips_situation_and_incident(tmp_path) -> None:
    repository = SQLiteDomainRepository(tmp_path / "multisensor.sqlite3")
    situation = Situation(
        id="situation:1",
        situation_type="activity_detected",
        started_at=NOW,
        updated_at=NOW,
        confidence=0.4,
        observation_ids=("observation:1",),
        explanation="Actividad detectada.",
        payload={"source_event_id": "event:1"},
    )
    incident = Incident(
        id="incident:1",
        incident_type="possible_intrusion",
        started_at=NOW,
        updated_at=NOW,
        evidence_ids=("evidence:1",),
        confidence=0.8,
        explanation="Evidencia multisensor.",
    )

    repository.save_situation(situation)
    repository.save_incident(incident)

    assert repository.get_situation(situation.id) == situation
    assert repository.all_situations() == (situation,)
    assert repository.get_incident(incident.id) == incident
    assert repository.all_incidents() == (incident,)


def test_sqlite_repository_rejects_duplicate_domain_ids(tmp_path) -> None:
    repository = SQLiteDomainRepository(tmp_path / "multisensor.sqlite3")
    situation = Situation(
        id="situation:1",
        situation_type="activity_detected",
        started_at=NOW,
        updated_at=NOW,
        confidence=0.4,
    )
    repository.save_situation(situation)

    with pytest.raises(RepositoryError, match="situación duplicada"):
        repository.save_situation(situation)
