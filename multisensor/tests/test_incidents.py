"""Pruebas del motor de incidentes."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from multisensor.contracts import Location, Observation
from multisensor.correlation import TemporalSpatialCorrelator
from multisensor.fusion import FusionEngine
from multisensor.incidents import IncidentEngine, IncidentPolicy


UTC = timezone.utc


def make_observation(identifier: str, sensor_type: str, confidence: float) -> Observation:
    return Observation(
        id=identifier,
        sensor_id=f"{sensor_type}-1",
        sensor_type=sensor_type,
        timestamp=datetime(2026, 9, 28, 19, 20, tzinfo=UTC),
        event_type="person_detected" if sensor_type == "camera" else "motion" if sensor_type == "pir" else "human_motion",
        confidence=confidence,
        location=Location(43.24, -5.34),
        payload={"motion": True} if sensor_type == "pir" else {},
        source="test",
    )


class IncidentEngineTests(unittest.TestCase):
    def _bundle(self):
        observations = [
            make_observation("cam-1", "camera", 0.9),
            make_observation("pir-1", "pir", 0.8),
            make_observation("wifi-1", "wifi_csi", 0.85),
        ]
        correlator = TemporalSpatialCorrelator()
        correlator.ingest(observations[0])
        correlator.ingest(observations[1])
        correlation = correlator.ingest(observations[2])
        assert correlation is not None
        bundle = FusionEngine().fuse(correlation, observations)
        return observations, correlation, bundle

    def test_three_independent_sensors_create_explainable_incident(self) -> None:
        observations, correlation, bundle = self._bundle()

        incident = IncidentEngine().evaluate(bundle, correlation.event)

        self.assertIsNotNone(incident)
        assert incident is not None
        self.assertEqual(incident.incident_type, "possible_intrusion")
        self.assertEqual(len(incident.evidence_ids), 3)
        self.assertEqual(incident.payload["sensor_count"], 3)
        self.assertEqual(incident.payload["source_event_id"], correlation.event.id)
        self.assertIn("sensores independientes", incident.explanation)
        self.assertNotIn("telegram", incident.payload)

    def test_two_sensors_do_not_create_incident(self) -> None:
        observations = [make_observation("cam-1", "camera", 0.9), make_observation("pir-1", "pir", 0.8)]
        correlator = TemporalSpatialCorrelator()
        correlator.ingest(observations[0])
        correlation = correlator.ingest(observations[1])
        assert correlation is not None
        bundle = FusionEngine().fuse(correlation, observations)

        self.assertIsNone(IncidentEngine().evaluate(bundle, correlation.event))

    def test_policy_can_raise_confidence_threshold_and_deduplicate(self) -> None:
        _, correlation, bundle = self._bundle()
        engine = IncidentEngine(IncidentPolicy(minimum_confidence=0.99))
        self.assertIsNone(engine.evaluate(bundle, correlation.event))

        permissive = IncidentEngine(IncidentPolicy(minimum_confidence=0.1))
        first = permissive.evaluate(bundle, correlation.event)
        second = permissive.evaluate(bundle, correlation.event)
        self.assertIsNotNone(first)
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
