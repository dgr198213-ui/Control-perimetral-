"""Pruebas de la normalización de entradas de sensor."""
from __future__ import annotations

import unittest

from multisensor.normalization import NormalizationError, normalize_observation


class ObservationNormalizationTests(unittest.TestCase):
    def test_normalizes_complete_camera_observation(self) -> None:
        observation = normalize_observation(
            {
                "id": "obs-cam-001",
                "sensor_id": "camera-front",
                "sensor_type": "camera",
                "timestamp": "2026-09-28T19:20:14Z",
                "event_type": "person_detected",
                "confidence": 0.91,
                "location": {"lat": 43.24, "lon": -5.34},
                "payload": {"track_id": "person-42", "bbox": [120, 80, 300, 500]},
                "source": "fixture",
            }
        )

        self.assertEqual(observation.id, "obs-cam-001")
        self.assertEqual(observation.timestamp.isoformat(), "2026-09-28T19:20:14+00:00")
        self.assertEqual(observation.location.latitude, 43.24)
        self.assertEqual(observation.location.longitude, -5.34)
        self.assertEqual(observation.payload["track_id"], "person-42")

    def test_uses_default_source_and_flat_coordinates(self) -> None:
        observation = normalize_observation(
            {
                "id": "obs-pir-001",
                "sensor_id": "pir-garden",
                "sensor_type": "pir",
                "timestamp": "2026-09-28T19:20:15+02:00",
                "event_type": "motion",
                "confidence": 0.78,
                "latitude": 43.241,
                "longitude": -5.341,
            },
            default_source="test-adapter",
        )

        self.assertEqual(observation.source, "test-adapter")
        self.assertEqual(observation.timestamp.isoformat(), "2026-09-28T17:20:15+00:00")
        self.assertEqual(observation.location.to_dict(), {"latitude": 43.241, "longitude": -5.341})

    def test_supports_observation_without_location(self) -> None:
        observation = normalize_observation(
            {
                "id": "obs-wifi-001",
                "sensor_id": "wifi-node-01",
                "sensor_type": "wifi_csi",
                "timestamp": "2026-09-28T19:20:16Z",
                "event_type": "human_motion",
                "confidence": 0.84,
            }
        )

        self.assertIsNone(observation.location)
        self.assertEqual(dict(observation.payload), {})

    def test_rejects_missing_required_field(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "sensor_id"):
            normalize_observation(
                {
                    "id": "obs-1",
                    "sensor_type": "pir",
                    "timestamp": "2026-09-28T19:20:16Z",
                    "event_type": "motion",
                    "confidence": 0.84,
                }
            )

    def test_rejects_naive_timestamp_and_partial_location(self) -> None:
        base = {
            "id": "obs-1",
            "sensor_id": "pir-garden",
            "sensor_type": "pir",
            "event_type": "motion",
            "confidence": 0.84,
        }
        with self.assertRaisesRegex(NormalizationError, "zona horaria"):
            normalize_observation({**base, "timestamp": "2026-09-28T19:20:16"})
        with self.assertRaisesRegex(NormalizationError, "latitude y longitude"):
            normalize_observation({**base, "timestamp": "2026-09-28T19:20:16Z", "location": {"lat": 43.24}})

    def test_rejects_non_mapping_input(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "objeto clave-valor"):
            normalize_observation(["not", "an", "observation"])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
