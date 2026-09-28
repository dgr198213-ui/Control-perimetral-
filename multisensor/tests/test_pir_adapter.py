"""Pruebas del adaptador PIR y del despacho multisensor."""
from __future__ import annotations

from datetime import timezone
import unittest

from multisensor.adapters import PirAdapterError, message_to_observation, pir_message_to_observation


class PirAdapterTests(unittest.TestCase):
    def test_converts_active_motion_with_default_confidence(self) -> None:
        observation = pir_message_to_observation(
            {
                "sensor_id": "pir-garden",
                "timestamp": "2026-09-28T19:20:15+02:00",
                "motion": True,
                "location": {"lat": 43.241, "lon": -5.341},
                "gpio": 17,
            }
        )

        self.assertEqual(observation.id, "pir:pir-garden:2026-09-28T17:20:15+00:00")
        self.assertEqual(observation.sensor_id, "pir-garden")
        self.assertEqual(observation.sensor_type, "pir")
        self.assertEqual(observation.event_type, "motion")
        self.assertEqual(observation.confidence, 1.0)
        self.assertEqual(observation.timestamp.tzinfo, timezone.utc)
        self.assertTrue(observation.payload["motion"])
        self.assertEqual(observation.payload["gpio"], 17)
        self.assertEqual(observation.location.to_dict(), {"latitude": 43.241, "longitude": -5.341})

    def test_converts_clear_state_with_explicit_confidence(self) -> None:
        observation = pir_message_to_observation(
            {
                "id": "pir-event-2",
                "sensor_id": "pir-garden",
                "timestamp": 1790623215.0,
                "state": "clear",
                "confidence": 0.2,
            }
        )

        self.assertEqual(observation.id, "pir:pir-event-2")
        self.assertEqual(observation.event_type, "motion_cleared")
        self.assertEqual(observation.confidence, 0.2)
        self.assertFalse(observation.payload["motion"])
        self.assertEqual(observation.payload["state"], "clear")

    def test_accepts_common_active_state_and_explicit_event_id(self) -> None:
        observation = pir_message_to_observation(
            {
                "event_id": "evt-pir-3",
                "sensor_id": "pir-entrance",
                "timestamp": "2026-09-28T19:20:16Z",
                "event_type": "triggered",
                "active": True,
                "battery": 87,
            }
        )

        self.assertEqual(observation.id, "pir:evt-pir-3")
        self.assertTrue(observation.payload["motion"])
        self.assertEqual(observation.payload["battery"], 87)

    def test_common_dispatch_sends_pir_into_same_observation_flow(self) -> None:
        observation = message_to_observation(
            "pir",
            {
                "sensor_id": "pir-room",
                "timestamp": "2026-09-28T19:20:17Z",
                "motion": True,
            },
        )

        self.assertEqual(observation.sensor_type, "pir")
        self.assertEqual(observation.source, "pir")

    def test_rejects_missing_or_invalid_pir_fields(self) -> None:
        base = {"sensor_id": "pir-room", "timestamp": "2026-09-28T19:20:17Z", "motion": True}
        with self.assertRaisesRegex(PirAdapterError, "sensor_id"):
            pir_message_to_observation({**base, "sensor_id": ""})
        with self.assertRaisesRegex(PirAdapterError, "timestamp"):
            pir_message_to_observation({key: value for key, value in base.items() if key != "timestamp"})
        with self.assertRaisesRegex(PirAdapterError, "booleano"):
            pir_message_to_observation({**base, "motion": "yes"})
        with self.assertRaisesRegex(PirAdapterError, "reconocido"):
            pir_message_to_observation({key: value for key, value in base.items() if key != "motion"} | {"state": "unknown"})
        with self.assertRaisesRegex(PirAdapterError, "entre 0 y 1"):
            pir_message_to_observation({**base, "confidence": 1.2})

    def test_rejects_invalid_location_and_unknown_dispatch_type(self) -> None:
        with self.assertRaisesRegex(PirAdapterError, "Ubicación"):
            pir_message_to_observation(
                {
                    "sensor_id": "pir-room",
                    "timestamp": "2026-09-28T19:20:17Z",
                    "motion": True,
                    "location": {"lat": 91, "lon": 0},
                }
            )
        with self.assertRaisesRegex(ValueError, "no soportado"):
            message_to_observation("audio", {})


if __name__ == "__main__":
    unittest.main()
