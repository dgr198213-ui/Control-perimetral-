"""Adaptador WiFi-CSI de posicionamiento agregado del perímetro."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from multisensor.contracts import ContractValidationError, Location, Observation
from multisensor.positioning import Anchor, PositioningError, triangulate
from multisensor.privacy import PrivacyViolation


class WifiCsiAdapterError(ValueError):
    """Evento WiFi-CSI inválido o no permitido."""


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(float(value)):
        parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise WifiCsiAdapterError("timestamp WiFi-CSI no es ISO 8601 válido") from exc
    else:
        raise WifiCsiAdapterError("WiFi-CSI requiere timestamp")
    if parsed.tzinfo is None:
        raise WifiCsiAdapterError("timestamp WiFi-CSI requiere zona horaria")
    return parsed.astimezone(timezone.utc)


def _location(message: Mapping[str, Any]) -> tuple[Location | None, dict[str, Any]]:
    if "position" in message:
        position = message["position"]
        if not isinstance(position, Mapping) or not all(key in position for key in ("x", "y")):
            raise WifiCsiAdapterError("position requiere x e y")
        try:
            x, y = float(position["x"]), float(position["y"])
        except (TypeError, ValueError) as exc:
            raise WifiCsiAdapterError("position x e y deben ser numéricos") from exc
        if not all(isfinite(value) for value in (x, y)):
            raise WifiCsiAdapterError("position no es finita")
        return None, {"position": {"x": round(x, 4), "y": round(y, 4)}}
    measurements = message.get("measurements")
    if measurements is None:
        raise WifiCsiAdapterError("WiFi-CSI requiere position o measurements")
    if not isinstance(measurements, Mapping) or len(measurements) != 3:
        raise WifiCsiAdapterError("measurements requiere exactamente tres anclas")
    anchors_raw = message.get("anchors")
    if not isinstance(anchors_raw, list) or len(anchors_raw) != 3:
        raise WifiCsiAdapterError("anchors requiere tres puntos calibrados")
    try:
        anchors = tuple(Anchor(str(item["id"]), float(item["x"]), float(item["y"])) for item in anchors_raw)
        x, y, calculated_confidence = triangulate({str(k): float(v) for k, v in measurements.items()}, anchors)
    except (KeyError, TypeError, ValueError, PositioningError) as exc:
        raise WifiCsiAdapterError(f"triangulación WiFi-CSI inválida: {exc}") from exc
    return None, {"position": {"x": x, "y": y}, "measurements": {str(k): float(v) for k, v in measurements.items()}, "triangulation_confidence": calculated_confidence}


def wifi_csi_message_to_observation(message: Mapping[str, Any]) -> Observation:
    if not isinstance(message, Mapping):
        raise WifiCsiAdapterError("evento WiFi-CSI debe ser un objeto")
    sensor_id = message.get("sensor_id")
    if not isinstance(sensor_id, str) or not sensor_id.startswith("wifi-csi-"):
        raise WifiCsiAdapterError("sensor_id WiFi-CSI debe pertenecer al perímetro autorizado")
    if any(key.lower() in {"bssid", "mac", "ssid", "imei", "imsi", "device_id", "license_plate"} for key in message):
        raise WifiCsiAdapterError("identificador WiFi no permitido")
    timestamp = _timestamp(message.get("timestamp"))
    raw_confidence = message.get("confidence")
    if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float)) or not 0 <= float(raw_confidence) <= 1:
        raise WifiCsiAdapterError("confidence WiFi-CSI debe estar entre 0 y 1")
    _, payload = _location(message)
    supplied_id = message.get("id", f"{sensor_id}:{timestamp.isoformat()}")
    try:
        return Observation(
            id=f"wifi-csi:{str(supplied_id).strip()}",
            sensor_id=sensor_id.strip(),
            sensor_type="wifi_csi",
            timestamp=timestamp,
            event_type="position_estimated",
            confidence=float(raw_confidence),
            location=None,
            payload=payload,
            source="wifi-csi-position",
        )
    except ContractValidationError as exc:
        raise WifiCsiAdapterError(str(exc)) from exc
