"""Pruebas de persistencia en memoria del MVP."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from multisensor.contracts import Evidence, Incident, Observation
from multisensor.persistence import (
    InMemoryEvidenceRepository,
    InMemoryIncidentRepository,
    InMemoryObservationRepository,
    RepositoryError,
)


UTC = timezone.utc


class MemoryRepositoryTests(unittest.TestCase):
    def test_observation_repository_round_trip_and_duplicate_guard(self) -> None:
        repository = InMemoryObservationRepository()
        observation = Observation(
            id="obs-1",
            sensor_id="pir-1",
            sensor_type="pir",
            timestamp=datetime(2026, 9, 28, 19, 20, tzinfo=UTC),
            event_type="motion",
            confidence=0.9,
            payload={"motion": True},
            source="test",
        )

        self.assertIs(repository.save(observation), observation)
        self.assertEqual(repository.get("obs-1"), observation)
        self.assertEqual(repository.all(), (observation,))
        with self.assertRaisesRegex(RepositoryError, "duplicada"):
            repository.save(observation)

    def test_evidence_and_incident_repositories_are_typed_and_independent(self) -> None:
        evidence_repository = InMemoryEvidenceRepository()
        incident_repository = InMemoryIncidentRepository()
        evidence = Evidence(
            id="evidence:1",
            event_id="event:1",
            sensor_id="pir-1",
            observed_at=datetime(2026, 9, 28, 19, 20, tzinfo=UTC),
            evidence_type="motion",
            confidence=0.8,
        )
        incident = Incident(
            id="incident:1",
            incident_type="possible_intrusion",
            started_at=datetime(2026, 9, 28, 19, 20, tzinfo=UTC),
            updated_at=datetime(2026, 9, 28, 19, 20, tzinfo=UTC),
            evidence_ids=("evidence:1",),
            confidence=0.8,
            explanation="Prueba auditable.",
        )

        evidence_repository.save(evidence)
        incident_repository.save(incident)
        self.assertEqual(evidence_repository.get(evidence.id), evidence)
        self.assertEqual(incident_repository.get(incident.id), incident)
        self.assertEqual(evidence_repository.all(), (evidence,))
        self.assertEqual(incident_repository.all(), (incident,))

        with self.assertRaisesRegex(RepositoryError, "se requiere Evidence"):
            evidence_repository.save(incident)  # type: ignore[arg-type]
        with self.assertRaisesRegex(RepositoryError, "se requiere Incident"):
            incident_repository.save(evidence)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
