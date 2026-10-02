from __future__ import annotations

from datetime import timezone
import unittest

from multisensor.adapters import WifiCsiAdapterError, message_to_observation, wifi_csi_message_to_observation


ANCHORS = [
    {"id": "sensor_a", "x": 0, "y": 0},
    {"id": "sensor_b", "x": 10, "y": 0},
    {"id": "sensor_c", "x": 0, "y": 10},
]


class WifiCsiAdapterTests(unittest.TestCase):
    def test_accepts_minimal_gateway_position(self) -> None:
        observation = wifi_csi_message_to_observation({
            "sensor_id": "wifi-csi-01",
            "timestamp": "2026-09-28T19:20:16+02:00",
            "position": {"x": 12.4, "y": 8.7},
            "confidence": 0.84,
        })
        self.assertEqual(observation.sensor_type, "wifi_csi")
        self.assertEqual(observation.event_type, "position_estimated")
        self.assertEqual(observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(observation.payload["position"], {"x": 12.4, "y": 8.7})

    def test_triangulates_three_anchors(self) -> None:
        observation = wifi_csi_message_to_observation({
            "sensor_id": "wifi-csi-01",
            "timestamp": "2026-10-01T20:00:00Z",
            "measurements": {"sensor_a": 7.0710678, "sensor_b": 7.0710678, "sensor_c": 7.0710678},
            "anchors": ANCHORS,
            "confidence": 0.82,
        })
        self.assertEqual(observation.payload["position"], {"x": 5.0, "y": 5.0})
        self.assertGreaterEqual(observation.payload["triangulation_confidence"], 0.99)

    def test_dispatches_wifi_alias_into_common_observation_flow(self) -> None:
        observation = message_to_observation(
            "wifi-csi",
            {"id": "wifi-event-1", "sensor_id": "wifi-csi-01", "timestamp": "2026-09-28T19:20:16Z", "confidence": 0.84, "position": {"x": 1.2, "y": 2.3}},
        )
        self.assertEqual(observation.id, "wifi-csi:wifi-event-1")
        self.assertEqual(observation.source, "wifi-csi-position")

    def test_rejects_identifiers_and_invalid_positioning(self) -> None:
        base = {"sensor_id": "wifi-csi-01", "timestamp": "2026-09-28T19:20:16Z", "confidence": 0.84, "position": {"x": 1, "y": 2}}
        with self.assertRaisesRegex(WifiCsiAdapterError, "identificador"):
            wifi_csi_message_to_observation({**base, "bssid": "AA:BB:CC:DD:EE:FF"})
        with self.assertRaisesRegex(WifiCsiAdapterError, "perímetro"):
            wifi_csi_message_to_observation({**base, "sensor_id": "wifi-node-01"})
        with self.assertRaisesRegex(WifiCsiAdapterError, "position"):
            wifi_csi_message_to_observation({**base, "position": {"x": "x", "y": 2}})


if __name__ == "__main__":
    unittest.main()
