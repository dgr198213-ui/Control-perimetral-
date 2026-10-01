"""Controles de privacidad para datos públicos y señales multisensor.

No intenta identificar personas ni dispositivos. Su objetivo es evitar que una
fuente pública se convierta accidentalmente en un rastreador individual.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class PrivacyViolation(ValueError):
    """Indica que un payload contiene identificadores no permitidos."""


FORBIDDEN_KEYS = frozenset({
    "bssid", "mac", "mac_address", "ssid", "imei", "imsi", "cell_id",
    "device_id", "advertising_id", "phone", "email", "face_embedding",
    "license_plate", "plate", "person_name",
})


@dataclass(frozen=True, slots=True)
class PublicResourcePolicy:
    """Política explícita para representar una fuente pública sin seguimiento."""

    source: str
    precision_decimals: int = 3
    retention_seconds: int = 3600

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise PrivacyViolation("source no puede estar vacío")
        if not 0 <= self.precision_decimals <= 6:
            raise PrivacyViolation("precision_decimals debe estar entre 0 y 6")
        if self.retention_seconds <= 0:
            raise PrivacyViolation("retention_seconds debe ser positivo")


def _round_coordinate(value: float, decimals: int) -> float:
    return round(float(value), decimals)


def validate_wifi_csi_payload(payload: Mapping[str, Any], *, sensor_prefix: str = "wifi-csi-") -> dict[str, Any]:
    """Valida una muestra agregada de un sensor WiFi-CSI propio."""
    if not isinstance(payload, Mapping):
        raise PrivacyViolation("WiFi-CSI requiere un objeto")
    sensor_id = payload.get("sensor_id")
    if not isinstance(sensor_id, str) or not sensor_id.startswith(sensor_prefix):
        raise PrivacyViolation("sensor_id WiFi-CSI debe pertenecer al perímetro autorizado")

    def walk(value: Any, key: str = "") -> None:
        if key.lower() in FORBIDDEN_KEYS:
            raise PrivacyViolation(f"identificador no permitido: {key}")
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                walk(child_value, str(child_key))
        elif isinstance(value, (list, tuple)):
            for child_value in value:
                walk(child_value, key)

    walk(payload)
    features = payload.get("features", {})
    if not isinstance(features, Mapping):
        raise PrivacyViolation("features WiFi-CSI debe ser un objeto agregado")
    allowed = {"motion_score", "activity_score", "amplitude_variance", "phase_variance", "channel_count", "window_ms"}
    unknown = sorted(set(features) - allowed)
    if unknown:
        raise PrivacyViolation(f"features no agregadas o no permitidas: {', '.join(unknown)}")
    normalized = dict(payload)
    normalized["sensor_id"] = sensor_id.strip()
    normalized["features"] = dict(features)
    return normalized


def sanitize_public_resource(payload: Mapping[str, Any], policy: PublicResourcePolicy) -> dict[str, Any]:
    """Devuelve un recurso público minimizado y rechaza identificadores sensibles."""
    forbidden = sorted(key for key in payload if key.lower() in FORBIDDEN_KEYS)
    if forbidden:
        raise PrivacyViolation(f"identificadores no permitidos: {', '.join(forbidden)}")
    result: dict[str, Any] = {
        "source": policy.source,
        "resource_id": str(payload.get("resource_id") or payload.get("id") or ""),
        "label": str(payload.get("label") or "recurso público"),
        "public": True,
        "retention_seconds": policy.retention_seconds,
    }
    if "latitude" in payload and "longitude" in payload:
        result["location"] = {
            "latitude": _round_coordinate(payload["latitude"], policy.precision_decimals),
            "longitude": _round_coordinate(payload["longitude"], policy.precision_decimals),
        }
    if "url" in payload:
        result["url"] = str(payload["url"])
    return result
