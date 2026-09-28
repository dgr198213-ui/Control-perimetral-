"""Adaptador de eventos WiFi-CSI ya procesados al contrato canónico."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from multisensor.contracts import ContractValidationError, Location, Observation


class WifiCsiAdapterError(ValueError):
    """Indica que un evento WiFi-CSI no tiene formato canónico válido."""


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not isfinite(float(value)):
            raise WifiCsiAdapterError("timestamp WiFi-CSI no es finito")
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


def _location(message: Mapping[str, Any]) -> Location | None:
    raw = message.get("location")
    if raw is None:
        if not any(key in message for key in ("latitude", "longitude", "lat", "lon")):
            return None
        raw = message
    if not isinstance(raw, Mapping):
        raise WifiCsiAdapterError("location WiFi-CSI debe ser un objeto")
    latitude = raw.get("latitude", raw.get("lat"))
    longitude = raw.get("longitude", raw.get("lon"))
    if latitude is None or longitude is None:
        raise WifiCsiAdapterError("location WiFi-CSI requiere latitude y longitude")
    try:
        return Location(latitude=latitude, longitude=longitude)
    except (ContractValidationError, TypeError) as exc:
        raise WifiCsiAdapterError(f"ubicación WiFi-CSI no válida: {exc}") from exc


def wifi_csi_message_to_observation(message: Mapping[str, Any]) -> Observation:
    """Convierte un evento procesado WiFi-CSI en ``Observation``.

    El adaptador no interpreta muestras I/Q ni captura CSI bruto. Solo acepta
    eventos con características ya extraídas y conserva el mapa ``features``
    para que la decisión posterior sea reproducible.
    """
    if not isinstance(message, Mapping):
        raise WifiCsiAdapterError("evento WiFi-CSI debe ser un objeto")
    sensor_id = message.get("sensor_id")
    if not isinstance(sensor_id, str) or not sensor_id.strip():
        raise WifiCsiAdapterError("WiFi-CSI requiere sensor_id")
    timestamp = _timestamp(message.get("timestamp"))
    event_type = message.get("event_type", "human_motion")
    if not isinstance(event_type, str) or not event_type.strip():
        raise WifiCsiAdapterError("event_type WiFi-CSI debe ser texto no vacío")
    raw_confidence = message.get("confidence")
    if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float)):
        raise WifiCsiAdapterError("confidence WiFi-CSI debe ser numérica")
    confidence = float(raw_confidence)
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise WifiCsiAdapterError("confidence WiFi-CSI debe estar entre 0 y 1")
    features = message.get("features", {})
    if not isinstance(features, Mapping):
        raise WifiCsiAdapterError("features WiFi-CSI debe ser un objeto")
    normalized_features = dict(features)
    event_id = message.get("id", message.get("event_id"))
    if event_id is None or (isinstance(event_id, str) and not event_id.strip()):
        event_id = f"{sensor_id}:{timestamp.isoformat()}"
    try:
        return Observation(
            id=f"wifi-csi:{str(event_id).strip()}",
            sensor_id=sensor_id.strip(),
            sensor_type="wifi_csi",
            timestamp=timestamp,
            event_type=event_type.strip(),
            confidence=confidence,
            location=_location(message),
            payload={"features": normalized_features, "sensor_id": sensor_id.strip()},
            source="wifi-csi",
        )
    except ContractValidationError as exc:
        raise WifiCsiAdapterError(str(exc)) from exc
