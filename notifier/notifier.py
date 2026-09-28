"""Notifica eventos de Frigate a Telegram sin enviar imágenes ni clips.

La notificación solo se habilita cuando existen los dos archivos de evidencia
montados en COMPLIANCE_DIR. El contenido de esos archivos no se transmite.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import requests

from multisensor.adapters import FrigateAdapterError, frigate_event_to_observation

LOG = logging.getLogger("perimetral-notifier")
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
COMPLIANCE_DIR = Path(os.getenv("COMPLIANCE_DIR", "/compliance"))
REQUIRED_EVIDENCE = (
    COMPLIANCE_DIR / "carteleria-verificada",
    COMPLIANCE_DIR / "encargo-tratamiento-firmado",
)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFY_ZONES = {
    zone.strip() for zone in os.getenv("NOTIFY_ZONES", "zona_perimetro").split(",") if zone.strip()
}
NOTIFIABLE_CLASSES = {"person", "car", "motorcycle", "bicycle"}
SEEN_EVENTS: set[str] = set()


def compliance_ready() -> bool:
    return all(path.is_file() for path in REQUIRED_EVIDENCE)


def telegram_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        LOG.exception("Error enviando la alerta textual a Telegram")


def on_connect(client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any = None) -> None:
    LOG.info("Conectado a MQTT (%s); suscribiendo a frigate/events", reason_code)
    client.subscribe("frigate/events", qos=1)


def on_message(_client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        LOG.warning("Evento MQTT no válido descartado")
        return

    try:
        observation = frigate_event_to_observation(payload)
    except FrigateAdapterError as exc:
        # Los eventos de actualización y los mensajes incompletos no alteran
        # el comportamiento operativo ni deben bloquear el suscriptor.
        if isinstance(payload, dict) and payload.get("type") == "new":
            LOG.warning("Observación Frigate no válida descartada: %s", exc)
        return

    event_id = str(observation.payload["frigate_event_id"])
    label = str(observation.payload["label"])
    camera = str(observation.payload["camera"])
    zones = set(observation.payload["zones"])
    LOG.info(
        "Observación canónica recibida: id=%s sensor=%s tipo=%s confianza=%.3f",
        observation.id,
        observation.sensor_id,
        observation.event_type,
        observation.confidence,
    )

    if event_id and event_id in SEEN_EVENTS:
        return
    if label not in NOTIFIABLE_CLASSES or not (zones & NOTIFY_ZONES):
        return
    if not compliance_ready():
        LOG.warning("Evento %s descartado: falta evidencia de cumplimiento", event_id or "sin-id")
        return
    if not telegram_configured():
        LOG.error("Telegram no configurado; alerta no enviada")
        return

    if event_id:
        SEEN_EVENTS.add(event_id)
        if len(SEEN_EVENTS) > 10000:
            SEEN_EVENTS.clear()

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %z")
    zone_text = ", ".join(sorted(zones & NOTIFY_ZONES))
    send_telegram(f"Detección: {label}\nCámara: {camera}\nZona: {zone_text}\nHora: {timestamp}")


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    if not compliance_ready():
        LOG.warning("Modo bloqueado: no se enviarán alertas hasta acreditar cartelería y encargo firmado")
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except (OSError, mqtt.MqttError):
            LOG.exception("MQTT no disponible; reintentando en 5 segundos")
            time.sleep(5)


if __name__ == "__main__":
    main()
