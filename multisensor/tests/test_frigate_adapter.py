"""Pruebas del adaptador de eventos Frigate."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from multisensor.adapters import FrigateAdapterError, frigate_event_to_observation


class FrigateAdapterTests(unittest.TestCase):
    def test_converts_new_event_to_observation(self) -> None:
        observation = frigate_event_to_observation(
            {
                "type": "new",
                "after": {
                    "id": "evt-123",
                    "camera": "camara_1",
                    "label": "person",
                    "start_time": 1790623214.0,
                    "top_score": 0.91,
                    "current_zones": ["zona_perimetro", "zona_perimetro"],
                    "location": {"lat": 43.24, "lon": -5.34},
                    "box": [0.1, 0.2, 0.5, 0.8],
                },
            }
        )

        self.assertEqual(observation.id, "frigate:evt-123")
        self.assertEqual(observation.sensor_id, "frigate:camara_1")
        self.assertEqual(observation.sensor_type, "camera")
        self.assertEqual(observation.event_type, "person_detected")
        self.assertEqual(observation.confidence, 0.91)
        self.assertEqual(observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(observation.location.to_dict(), {"latitude": 43.24, "longitude": -5.34})
        self.assertEqual(observation.payload["zones"], ["zona_perimetro"])
        self.assertEqual(observation.payload["frigate_event_id"], "evt-123")

    def test_accepts_iso_timestamp_and_score_fallback(self) -> None:
        observation = frigate_event_to_observation(
            {
                "type": "new",
                "after": {
                    "id": "evt-456",
                    "camera": "camara_2",
                    "label": "car",
                    "timestamp": "2026-09-28T19:20:14+02:00",
                    "score": 0.72,
                },
            }
        )

        self.assertEqual(observation.timestamp.isoformat(), "2026-09-28T17:20:14+00:00")
        self.assertEqual(observation.confidence, 0.72)
        self.assertIsNone(observation.location)
        self.assertEqual(observation.payload["zones"], [])

    def test_keeps_frigate_payload_traceable_without_credentials(self) -> None:
        observation = frigate_event_to_observation(
            {
                "type": "new",
                "after": {
                    "id": "evt-789",
                    "camera": "camara_1",
                    "label": "person",
                    "start_time": datetime(2026, 9, 28, 19, 20, tzinfo=timezone.utc),
                    "top_score": 0.83,
                    "sub_label": ["unknown", 0.4],
                    "attributes": {"face": 0.1},
                },
            }
        )

        self.assertEqual(observation.payload["sub_label"], ["unknown", 0.4])
        self.assertNotIn("password", observation.payload)
        self.assertEqual(observation.source, "frigate")

    def test_rejects_non_new_event(self) -> None:
        with self.assertRaisesRegex(FrigateAdapterError, "tipo new"):
            frigate_event_to_observation({"type": "update", "after": {}})

    def test_rejects_malformed_event_and_invalid_confidence(self) -> None:
        base = {
            "type": "new",
            "after": {
                "id": "evt-1",
                "camera": "camara_1",
                "label": "person",
                "start_time": 1790623214.0,
                "top_score": 0.8,
            },
        }
        with self.assertRaisesRegex(FrigateAdapterError, "camera"):
            frigate_event_to_observation({"type": "new", "after": {**base["after"], "camera": ""}})
        with self.assertRaisesRegex(FrigateAdapterError, "entre 0 y 1"):
            frigate_event_to_observation(
                {"type": "new", "after": {**base["after"], "top_score": 1.2}}
            )
        with self.assertRaisesRegex(FrigateAdapterError, "start_time o timestamp"):
            frigate_event_to_observation(
                {"type": "new", "after": {key: value for key, value in base["after"].items() if key != "start_time"}}
            )

    def test_rejects_invalid_location_and_zones(self) -> None:
        base = {
            "type": "new",
            "after": {
                "id": "evt-1",
                "camera": "camara_1",
                "label": "person",
                "start_time": 1790623214.0,
                "top_score": 0.8,
            },
        }
        with self.assertRaisesRegex(FrigateAdapterError, "Ubicación"):
            frigate_event_to_observation(
                {"type": "new", "after": {**base["after"], "location": {"lat": 95, "lon": 0}}}
            )
        with self.assertRaisesRegex(FrigateAdapterError, "zones"):
            frigate_event_to_observation(
                {"type": "new", "after": {**base["after"], "zones": "zona_perimetro"}}
            )


if __name__ == "__main__":
    unittest.main()
