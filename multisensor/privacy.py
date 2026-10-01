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
