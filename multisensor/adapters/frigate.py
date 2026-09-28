"""Adaptador de eventos Frigate al contrato canónico multisensor.

El adaptador es puro: no se conecta a MQTT, no consulta archivos de cumplimiento
ni envía alertas. La integración con el flujo existente se hará en una fase
posterior y explícita.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from multisensor.contracts import ContractValidationError, Location, Observation


class FrigateAdapterError(ValueError):
    """Indica que un evento de Frigate no tiene un formato utilizable."""


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FrigateAdapterError(f"El evento Frigate requiere {field_name}")
    return value.strip()


def _event_body(message: Mapping[str, Any]) -> Mapping[str, Any]:
    after = message.get("after")
    if not isinstance(after, Mapping):
        raise FrigateAdapterError("El evento Frigate requiere el objeto after")
    return after


def _timestamp(after: Mapping[str, Any]) -> datetime:
    raw_timestamp = after.get("start_time", after.get("timestamp"))
    if isinstance(raw_timestamp, datetime):
        value = raw_timestamp
    elif isinstance(raw_timestamp, (int, float)) and not isinstance(raw_timestamp, bool):
        if not isfinite(float(raw_timestamp)):
            raise FrigateAdapterError("La marca temporal de Frigate no es finita")
        value = datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc)
    elif isinstance(raw_timestamp, str):
        try:
            value = datetime.fromisoformat(raw_timestamp.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise FrigateAdapterError("La marca temporal de Frigate no es ISO 8601 válida") from exc
    else:
        raise FrigateAdapterError("El evento Frigate requiere start_time o timestamp")

    if value.tzinfo is None:
        raise FrigateAdapterError("La marca temporal de Frigate requiere zona horaria")
    return value.astimezone(timezone.utc)


def _confidence(after: Mapping[str, Any]) -> float:
    raw_score = after.get("top_score", after.get("score"))
    if raw_score is None:
        raise FrigateAdapterError("El evento Frigate requiere top_score o score")
    if isinstance(raw_score, bool):
        raise FrigateAdapterError("La confianza de Frigate debe ser numérica")
    try:
        score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise FrigateAdapterError("La confianza de Frigate debe ser numérica") from exc
    if not isfinite(score) or not 0.0 <= score <= 1.0:
        raise FrigateAdapterError("La confianza de Frigate debe estar entre 0 y 1")
    return score


def _location(after: Mapping[str, Any]) -> Location | None:
    location = after.get("location")
    if location is None:
        return None
    if not isinstance(location, Mapping):
        raise FrigateAdapterError("location de Frigate debe ser un objeto")
    try:
        return Location(
            latitude=location.get("latitude", location.get("lat")),
            longitude=location.get("longitude", location.get("lon")),
        )
    except (ContractValidationError, TypeError) as exc:
        raise FrigateAdapterError(f"Ubicación de Frigate no válida: {exc}") from exc


def frigate_event_to_observation(message: Mapping[str, Any]) -> Observation:
    """Convierte un evento ``frigate/events`` de tipo ``new`` en Observation.

    Frigate publica cambios de estado adicionales, pero en esta primera fase
    solo un evento nuevo representa una observación atómica. Los datos propios
    de Frigate se conservan en ``payload`` para mantener trazabilidad.
    """
    if not isinstance(message, Mapping):
        raise FrigateAdapterError("El mensaje Frigate debe ser un objeto")
    if message.get("type") != "new":
        raise FrigateAdapterError("Solo se admiten eventos Frigate de tipo new")

    after = _event_body(message)
    event_id = _required_text(after.get("id", message.get("id")), "id")
    camera = _required_text(after.get("camera"), "camera")
    label = _required_text(after.get("label"), "label")
    timestamp = _timestamp(after)
    zones = after.get("current_zones", after.get("zones", [])) or []
    if not isinstance(zones, (list, tuple, set)):
        raise FrigateAdapterError("zones de Frigate debe ser una lista")
    normalized_zones = tuple(sorted({str(zone).strip() for zone in zones if str(zone).strip()}))

    payload = {
        "frigate_event_id": event_id,
        "camera": camera,
        "label": label,
        "zones": list(normalized_zones),
        "source_message_type": message.get("type"),
    }
    for key in ("box", "area", "score", "top_score", "sub_label", "attributes"):
        if key in after:
            payload[key] = after[key]

    try:
        return Observation(
            id=f"frigate:{event_id}",
            sensor_id=f"frigate:{camera}",
            sensor_type="camera",
            timestamp=timestamp,
            event_type=f"{label}_detected",
            confidence=_confidence(after),
            location=_location(after),
            payload=payload,
            source="frigate",
        )
    except ContractValidationError as exc:
        raise FrigateAdapterError(str(exc)) from exc
