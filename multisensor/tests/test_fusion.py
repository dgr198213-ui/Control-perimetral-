"""Pruebas del Evidence/Fusion Engine."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from multisensor.contracts import Location, Observation
from multisensor.correlation import TemporalSpatialCorrelator
from multisensor.fusion import FusionEngine, score_observation


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


class FusionTests(unittest.TestCase):
    def test_score_uses_product_not_sum(self) -> None:
        observation = make_observation("cam-1", "camera", 0.8)

        breakdown = score_observation(
            observation,
            temporal_factor=0.5,
            spatial_factor=0.8,
            sensor_reliability=0.9,
        )

        self.assertAlmostEqual(breakdown.score, 0.288)
        self.assertLess(breakdown.score, observation.confidence)

    def test_three_sensors_produce_auditable_evidence_bundle(self) -> None:
        observations = [
            make_observation("cam-1", "camera", 0.9),
            make_observation("pir-1", "pir", 0.8),
            make_observation("wifi-1", "wifi_csi", 0.85),
        ]
        correlator = TemporalSpatialCorrelator()
        correlator.ingest(observations[0])
        correlator.ingest(observations[1])
        correlation = correlator.ingest(observations[2])
        self.assertIsNotNone(correlation)
        assert correlation is not None

        bundle = FusionEngine().fuse(correlation, observations)

        self.assertEqual(len(bundle.evidences), 3)
        self.assertTrue(bundle.candidate_for_incident)
        self.assertEqual(bundle.event_id, correlation.event.id)
        self.assertEqual({item.payload["sensor_type"] for item in bundle.evidences}, {"camera", "pir", "wifi_csi"})
        self.assertIn("sensores independientes", bundle.explanation)

    def test_two_sensors_remain_event_evidence_but_not_incident_candidate(self) -> None:
        observations = [make_observation("cam-1", "camera", 0.9), make_observation("pir-1", "pir", 0.8)]
        correlator = TemporalSpatialCorrelator()
        correlator.ingest(observations[0])
        correlation = correlator.ingest(observations[1])
        self.assertIsNotNone(correlation)
        assert correlation is not None

        bundle = FusionEngine().fuse(correlation, observations)

        self.assertEqual(len(bundle.evidences), 2)
        self.assertFalse(bundle.candidate_for_incident)


if __name__ == "__main__":
    unittest.main()
