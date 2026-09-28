"""Contrato canónico para una observación producida por un sensor."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping


class ContractValidationError(ValueError):
    """Indica que un dato no cumple el contrato canónico multisensor."""


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} debe ser texto no vacío")
    return value.strip()


def _confidence(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractValidationError("confidence debe ser un número entre 0 y 1")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ContractValidationError("confidence debe estar entre 0 y 1")
    return normalized


@dataclass(frozen=True, slots=True)
class Location:
    """Posición geográfica opcional asociada a una observación o derivado."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if isinstance(self.latitude, bool) or not isinstance(self.latitude, (int, float)):
            raise ContractValidationError("latitude debe ser un número")
        if isinstance(self.longitude, bool) or not isinstance(self.longitude, (int, float)):
            raise ContractValidationError("longitude debe ser un número")

        latitude = float(self.latitude)
        longitude = float(self.longitude)
        if not -90.0 <= latitude <= 90.0:
            raise ContractValidationError("latitude debe estar entre -90 y 90")
        if not -180.0 <= longitude <= 180.0:
            raise ContractValidationError("longitude debe estar entre -180 y 180")

        object.__setattr__(self, "latitude", latitude)
        object.__setattr__(self, "longitude", longitude)

    def to_dict(self) -> dict[str, float]:
        return {"latitude": self.latitude, "longitude": self.longitude}


@dataclass(frozen=True, slots=True)
class Observation:
    """Señal atómica registrada por un sensor antes de cualquier correlación.

    Una observación no afirma una intrusión: conserva únicamente el hecho que
    el sensor reportó, su confianza y los metadatos necesarios para trazabilidad.
    """

    id: str
    sensor_id: str
    sensor_type: str
    timestamp: datetime
    event_type: str
    confidence: float
    location: Location | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    source: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required_text(self.id, "id"))
        object.__setattr__(self, "sensor_id", _required_text(self.sensor_id, "sensor_id"))
        object.__setattr__(self, "sensor_type", _required_text(self.sensor_type, "sensor_type"))
        object.__setattr__(self, "event_type", _required_text(self.event_type, "event_type"))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))

        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ContractValidationError("timestamp debe incluir zona horaria")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(timezone.utc))

        if self.location is not None and not isinstance(self.location, Location):
            raise ContractValidationError("location debe ser Location o None")
        if not isinstance(self.payload, Mapping):
            raise ContractValidationError("payload debe ser un objeto clave-valor")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        """Devuelve una representación apta para transporte y almacenamiento."""
        return {
            "id": self.id,
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "event_type": self.event_type,
            "confidence": self.confidence,
            "location": self.location.to_dict() if self.location else None,
            "payload": dict(self.payload),
            "source": self.source,
        }
