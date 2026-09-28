"""Normalización de mensajes de sensores al contrato canónico multisensor."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from multisensor.contracts import ContractValidationError, Location, Observation


class NormalizationError(ValueError):
    """Indica que una entrada de sensor no puede convertirse en Observation."""


def _required(raw: Mapping[str, Any], field_name: str) -> Any:
    value = raw.get(field_name)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise NormalizationError(f"Falta el campo obligatorio: {field_name}")
    return value


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise NormalizationError("timestamp debe usar formato ISO 8601 válido") from exc
    else:
        raise NormalizationError("timestamp debe ser datetime o texto ISO 8601")

    if parsed.tzinfo is None:
        raise NormalizationError("timestamp debe incluir zona horaria")
    return parsed


def _parse_location(raw: Mapping[str, Any]) -> Location | None:
    location = raw.get("location")
    if location is None:
        has_flat_coordinates = any(key in raw for key in ("latitude", "longitude", "lat", "lon"))
        if not has_flat_coordinates:
            return None
        location = raw

    if not isinstance(location, Mapping):
        raise NormalizationError("location debe ser un objeto con latitude y longitude")

    latitude = location.get("latitude", location.get("lat"))
    longitude = location.get("longitude", location.get("lon"))
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        raise NormalizationError("location debe incluir latitude y longitude")

    try:
        return Location(latitude=latitude, longitude=longitude)
    except ContractValidationError as exc:
        raise NormalizationError(str(exc)) from exc


def normalize_observation(raw: Mapping[str, Any], *, default_source: str = "unknown") -> Observation:
    """Convierte una entrada de sensor al formato canónico ``Observation``.

    Los adaptadores específicos de Frigate, PIR y Wi-Fi CSI se añadirán en
    fases posteriores. Esta función solo valida y normaliza el contrato común.
    """
    if not isinstance(raw, Mapping):
        raise NormalizationError("La observación de entrada debe ser un objeto clave-valor")

    source = raw.get("source", default_source)
    try:
        return Observation(
            id=_required(raw, "id"),
            sensor_id=_required(raw, "sensor_id"),
            sensor_type=_required(raw, "sensor_type"),
            timestamp=_parse_timestamp(_required(raw, "timestamp")),
            event_type=_required(raw, "event_type"),
            confidence=_required(raw, "confidence"),
            location=_parse_location(raw),
            payload=raw.get("payload", {}),
            source=source,
        )
    except ContractValidationError as exc:
        raise NormalizationError(str(exc)) from exc
