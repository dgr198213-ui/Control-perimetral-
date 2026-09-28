"""Pruebas del enlace MQTT -> adaptador Frigate del notificador."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


class _FakeClient:
    pass


class _FakeMessage:
    pass


class _FakeCallbackApiVersion:
    VERSION2 = 2


def _load_notifier():
    mqtt_client = types.ModuleType("paho.mqtt.client")
    mqtt_client.Client = _FakeClient
    mqtt_client.MQTTMessage = _FakeMessage
    mqtt_client.CallbackAPIVersion = _FakeCallbackApiVersion
    mqtt_package = types.ModuleType("paho")
    mqtt_package.__path__ = []
    mqtt_package.mqtt = types.ModuleType("paho.mqtt")
    mqtt_package.mqtt.__path__ = []
    mqtt_package.mqtt.client = mqtt_client
    requests_module = types.ModuleType("requests")
    requests_module.RequestException = Exception
    sys.modules.update(
        {
            "paho": mqtt_package,
            "paho.mqtt": mqtt_package.mqtt,
            "paho.mqtt.client": mqtt_client,
            "requests": requests_module,
        }
    )

    module_name = "notifier_under_test"
    spec = importlib.util.spec_from_file_location(
        module_name, Path(__file__).parents[1] / "notifier.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


notifier = _load_notifier()


class NotifierIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        notifier.SEEN_EVENTS.clear()
        notifier.LOG = Mock()
        notifier.NOTIFY_ZONES = {"zona_perimetro"}
        notifier.NOTIFIABLE_CLASSES = {"person"}
        notifier.compliance_ready = Mock(return_value=False)
        notifier.telegram_configured = Mock(return_value=False)
        notifier.send_telegram = Mock()

    def test_new_event_is_converted_before_compliance_filter(self) -> None:
        msg = _FakeMessage()
        msg.payload = json.dumps(
            {
                "type": "new",
                "after": {
                    "id": "evt-live-1",
                    "camera": "camara_1",
                    "label": "person",
                    "start_time": 1790623214.0,
                    "top_score": 0.91,
                    "current_zones": ["zona_perimetro"],
                },
            }
        ).encode("utf-8")

        notifier.on_message(None, None, msg)

        self.assertEqual(notifier.compliance_ready.call_count, 1)
        notifier.send_telegram.assert_not_called()
        log_text = " ".join(str(call) for call in notifier.LOG.info.call_args_list)
        self.assertIn("frigate:evt-live-1", log_text)
        self.assertIn("person_detected", log_text)

    def test_update_event_is_ignored_without_warning_or_alert(self) -> None:
        msg = _FakeMessage()
        msg.payload = json.dumps({"type": "update", "after": {}}).encode("utf-8")

        notifier.on_message(None, None, msg)

        notifier.LOG.warning.assert_not_called()
        notifier.send_telegram.assert_not_called()
        notifier.compliance_ready.assert_not_called()

    def test_non_object_json_is_dropped_without_crashing_callback(self) -> None:
        msg = _FakeMessage()
        msg.payload = json.dumps(["not", "an", "event"]).encode("utf-8")

        notifier.on_message(None, None, msg)

        notifier.LOG.warning.assert_not_called()
        notifier.send_telegram.assert_not_called()
        notifier.compliance_ready.assert_not_called()

    def test_malformed_new_event_is_dropped_without_crashing_callback(self) -> None:
        msg = _FakeMessage()
        msg.payload = json.dumps(
            {"type": "new", "after": {"id": "evt-bad", "camera": "camara_1"}}
        ).encode("utf-8")

        notifier.on_message(None, None, msg)

        notifier.LOG.warning.assert_called_once()
        notifier.send_telegram.assert_not_called()
        notifier.compliance_ready.assert_not_called()


if __name__ == "__main__":
    unittest.main()
