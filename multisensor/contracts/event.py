"""Contrato canónico para eventos derivados de observaciones."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .observation import ContractValidationError, Location, _confidence, _required_text


@dataclass(frozen=True, slots=True)
class Event:
    """Interpretación normalizada de una o más observaciones.

    Este contrato no emite alertas ni decide incidentes. Solo conserva la
    relación explícita con las observaciones de las que procede.
    """

    id: str
    event_type: str
    timestamp: datetime
    observation_ids: tuple[str, ...]
    confidence: float
    location: Location | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    source: str = "multisensor"

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required_text(self.id, "id"))
        object.__setattr__(self, "event_type", _required_text(self.event_type, "event_type"))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))

        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ContractValidationError("timestamp debe incluir zona horaria")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(timezone.utc))

        if not self.observation_ids:
            raise ContractValidationError("observation_ids debe incluir al menos una observación")
        normalized_ids = tuple(_required_text(item, "observation_id") for item in self.observation_ids)
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ContractValidationError("observation_ids no puede contener duplicados")
        object.__setattr__(self, "observation_ids", normalized_ids)

        if self.location is not None and not isinstance(self.location, Location):
            raise ContractValidationError("location debe ser Location o None")
        if not isinstance(self.payload, Mapping):
            raise ContractValidationError("payload debe ser un objeto clave-valor")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "observation_ids": list(self.observation_ids),
            "confidence": self.confidence,
            "location": self.location.to_dict() if self.location else None,
            "payload": dict(self.payload),
            "source": self.source,
        }
