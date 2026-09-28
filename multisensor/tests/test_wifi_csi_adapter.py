"""Pruebas del adaptador WiFi-CSI."""
from __future__ import annotations

from datetime import timezone
import unittest

from multisensor.adapters import WifiCsiAdapterError, message_to_observation, wifi_csi_message_to_observation


class WifiCsiAdapterTests(unittest.TestCase):
    def test_converts_processed_event_and_preserves_features(self) -> None:
        observation = wifi_csi_message_to_observation(
            {
                "sensor_id": "wifi-node-01",
                "timestamp": "2026-09-28T19:20:16+02:00",
                "event_type": "human_motion",
                "confidence": 0.84,
                "features": {"variance": 0.72, "fft_energy": 0.61, "threshold": 0.48},
                "location": {"lat": 43.24, "lon": -5.34},
            }
        )

        self.assertEqual(observation.id, "wifi-csi:wifi-node-01:2026-09-28T17:20:16+00:00")
        self.assertEqual(observation.sensor_type, "wifi_csi")
        self.assertEqual(observation.event_type, "human_motion")
        self.assertEqual(observation.confidence, 0.84)
        self.assertEqual(observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(observation.payload["features"]["fft_energy"], 0.61)
        self.assertEqual(observation.location.to_dict(), {"latitude": 43.24, "longitude": -5.34})

    def test_dispatches_wifi_alias_into_common_observation_flow(self) -> None:
        observation = message_to_observation(
            "wifi-csi",
            {
                "id": "wifi-event-1",
                "sensor_id": "wifi-node-01",
                "timestamp": "2026-09-28T19:20:16Z",
                "confidence": 0.84,
                "features": {"variance": 0.72},
            },
        )
        self.assertEqual(observation.id, "wifi-csi:wifi-event-1")
        self.assertEqual(observation.source, "wifi-csi")

    def test_rejects_raw_or_incomplete_events(self) -> None:
        base = {
            "sensor_id": "wifi-node-01",
            "timestamp": "2026-09-28T19:20:16Z",
            "confidence": 0.84,
            "features": {"variance": 0.72},
        }
        with self.assertRaisesRegex(WifiCsiAdapterError, "sensor_id"):
            wifi_csi_message_to_observation({**base, "sensor_id": ""})
        with self.assertRaisesRegex(WifiCsiAdapterError, "timestamp"):
            wifi_csi_message_to_observation({key: value for key, value in base.items() if key != "timestamp"})
        with self.assertRaisesRegex(WifiCsiAdapterError, "confidence.*entre"):
            wifi_csi_message_to_observation({**base, "confidence": 1.4})
        with self.assertRaisesRegex(WifiCsiAdapterError, "features"):
            wifi_csi_message_to_observation({**base, "features": [0.1, 0.2]})


if __name__ == "__main__":
    unittest.main()
