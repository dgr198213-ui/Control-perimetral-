"""Pruebas de los contratos canónicos del núcleo multisensor."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from multisensor.contracts import (
    ContractValidationError,
    Evidence,
    Event,
    Incident,
    Location,
    Observation,
)


UTC = timezone.utc
NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


class ContractTests(unittest.TestCase):
    def test_observation_normalizes_time_and_preserves_payload_immutably(self) -> None:
        observation = Observation(
            id="obs-camera-1",
            sensor_id="camera-front",
            sensor_type="camera",
            timestamp=NOW.astimezone(timezone(timedelta(hours=2))),
            event_type="person_detected",
            confidence=0.91,
            location=Location(43.24, -5.34),
            payload={"track_id": "person-42"},
            source="manual-test",
        )

        self.assertEqual(observation.timestamp, NOW)
        self.assertEqual(observation.location.to_dict(), {"latitude": 43.24, "longitude": -5.34})
        self.assertEqual(observation.to_dict()["payload"], {"track_id": "person-42"})
        with self.assertRaises(TypeError):
            observation.payload["track_id"] = "other"  # type: ignore[index]

    def test_location_rejects_coordinates_outside_the_world(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "latitude"):
            Location(91, 0)
        with self.assertRaisesRegex(ContractValidationError, "longitude"):
            Location(0, 181)

    def test_observation_requires_aware_time_and_bounded_confidence(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "zona horaria"):
            Observation(
                id="obs-1",
                sensor_id="pir-garden",
                sensor_type="pir",
                timestamp=datetime(2026, 9, 28, 12, 0),
                event_type="motion",
                confidence=0.5,
            )
        with self.assertRaisesRegex(ContractValidationError, "entre 0 y 1"):
            Observation(
                id="obs-1",
                sensor_id="pir-garden",
                sensor_type="pir",
                timestamp=NOW,
                event_type="motion",
                confidence=1.1,
            )

    def test_event_rejects_duplicate_observation_references(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "duplicados"):
            Event(
                id="evt-1",
                event_type="motion",
                timestamp=NOW,
                observation_ids=("obs-1", "obs-1"),
                confidence=0.8,
            )

    def test_evidence_and_incident_keep_auditable_references(self) -> None:
        evidence = Evidence(
            id="evidence-1",
            event_id="evt-1",
            sensor_id="camera-front",
            observed_at=NOW,
            evidence_type="person_detection",
            confidence=0.91,
            description="Persona detectada por la cámara frontal.",
        )
        incident = Incident(
            id="incident-1",
            incident_type="possible_intrusion",
            started_at=NOW,
            updated_at=NOW + timedelta(seconds=2),
            evidence_ids=(evidence.id,),
            confidence=0.91,
            explanation="Una evidencia de cámara requiere correlación posterior.",
        )

        self.assertEqual(evidence.to_dict()["event_id"], "evt-1")
        self.assertEqual(incident.to_dict()["evidence_ids"], ["evidence-1"])

    def test_incident_rejects_an_update_before_its_start(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "anterior"):
            Incident(
                id="incident-1",
                incident_type="possible_intrusion",
                started_at=NOW,
                updated_at=NOW - timedelta(seconds=1),
                evidence_ids=("evidence-1",),
                confidence=0.7,
            )


if __name__ == "__main__":
    unittest.main()
