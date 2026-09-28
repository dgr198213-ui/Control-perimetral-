"""Adaptador de lecturas PIR al contrato canónico multisensor."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from multisensor.contracts import ContractValidationError, Location, Observation


class PirAdapterError(ValueError):
    """Indica que una lectura PIR no tiene un formato utilizable."""


_ACTIVE_STATES = {"active", "motion", "detected", "on", "triggered"}
_INACTIVE_STATES = {"inactive", "clear", "no_motion", "off", "idle"}


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PirAdapterError(f"La lectura PIR requiere {field_name}")
    return value.strip()


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not isfinite(float(value)):
            raise PirAdapterError("La marca temporal PIR no es finita")
        parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise PirAdapterError("La marca temporal PIR no es ISO 8601 válida") from exc
    else:
        raise PirAdapterError("La lectura PIR requiere timestamp")

    if parsed.tzinfo is None:
        raise PirAdapterError("La marca temporal PIR requiere zona horaria")
    return parsed.astimezone(timezone.utc)


def _motion_state(message: Mapping[str, Any]) -> bool:
    if "motion" in message:
        motion = message["motion"]
        if not isinstance(motion, bool):
            raise PirAdapterError("motion debe ser booleano")
        return motion

    if "active" in message:
        active = message["active"]
        if not isinstance(active, bool):
            raise PirAdapterError("active debe ser booleano")
        return active

    raw_state = message.get("state", message.get("event_type"))
    if not isinstance(raw_state, str):
        raise PirAdapterError("La lectura PIR requiere motion, active o state")
    state = raw_state.strip().lower()
    if state in _ACTIVE_STATES:
        return True
    if state in _INACTIVE_STATES:
        return False
    raise PirAdapterError(f"Estado PIR no reconocido: {raw_state}")


def _confidence(message: Mapping[str, Any], motion: bool) -> float:
    raw_confidence = message.get("confidence", 1.0 if motion else 0.0)
    if isinstance(raw_confidence, bool):
        raise PirAdapterError("confidence PIR debe ser numérica")
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError) as exc:
        raise PirAdapterError("confidence PIR debe ser numérica") from exc
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise PirAdapterError("confidence PIR debe estar entre 0 y 1")
    return confidence


def _location(message: Mapping[str, Any]) -> Location | None:
    raw_location = message.get("location")
    if raw_location is None:
        if not any(key in message for key in ("latitude", "longitude", "lat", "lon")):
            return None
        raw_location = message
    if not isinstance(raw_location, Mapping):
        raise PirAdapterError("location PIR debe ser un objeto")

    latitude = raw_location.get("latitude", raw_location.get("lat"))
    longitude = raw_location.get("longitude", raw_location.get("lon"))
    if latitude is None or longitude is None:
        raise PirAdapterError("location PIR debe incluir latitude y longitude")
    try:
        return Location(latitude=latitude, longitude=longitude)
    except (ContractValidationError, TypeError) as exc:
        raise PirAdapterError(f"Ubicación PIR no válida: {exc}") from exc


def pir_message_to_observation(message: Mapping[str, Any]) -> Observation:
    """Convierte una lectura PIR en una ``Observation`` canónica.

    Se aceptan ``motion`` o ``active`` booleanos y estados textuales comunes.
    Una lectura sin identificador usa el sensor y el timestamp normalizado para
    formar un identificador determinista, evitando duplicados accidentales.
    """
    if not isinstance(message, Mapping):
        raise PirAdapterError("La lectura PIR debe ser un objeto")

    sensor_id = _required_text(message.get("sensor_id"), "sensor_id")
    timestamp = _timestamp(message.get("timestamp"))
    motion = _motion_state(message)
    confidence = _confidence(message, motion)
    event_id = message.get("id", message.get("event_id"))
    if event_id is None or (isinstance(event_id, str) and not event_id.strip()):
        event_id = f"{sensor_id}:{timestamp.isoformat()}"
    event_id = _required_text(str(event_id), "id")

    payload = {
        "sensor_id": sensor_id,
        "motion": motion,
        "state": "motion" if motion else "clear",
    }
    for key in ("gpio", "pin", "battery", "signal_strength"):
        if key in message:
            payload[key] = message[key]

    try:
        return Observation(
            id=f"pir:{event_id}",
            sensor_id=sensor_id,
            sensor_type="pir",
            timestamp=timestamp,
            event_type="motion" if motion else "motion_cleared",
            confidence=confidence,
            location=_location(message),
            payload=payload,
            source="pir",
        )
    except ContractValidationError as exc:
        raise PirAdapterError(str(exc)) from exc
