"""Contrato canónico para evidencia trazable asociada a un evento."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .observation import ContractValidationError, _confidence, _required_text


@dataclass(frozen=True, slots=True)
class Evidence:
    """Evidencia explícita que respalda un evento sin ampliar su significado.

    La evidencia describe qué sensor o dato sustentó una interpretación; no
    transforma por sí sola una señal débil en un incidente.
    """

    id: str
    event_id: str
    sensor_id: str
    observed_at: datetime
    evidence_type: str
    confidence: float
    description: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required_text(self.id, "id"))
        object.__setattr__(self, "event_id", _required_text(self.event_id, "event_id"))
        object.__setattr__(self, "sensor_id", _required_text(self.sensor_id, "sensor_id"))
        object.__setattr__(self, "evidence_type", _required_text(self.evidence_type, "evidence_type"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))

        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None:
            raise ContractValidationError("observed_at debe incluir zona horaria")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(timezone.utc))

        if not isinstance(self.description, str):
            raise ContractValidationError("description debe ser texto")
        object.__setattr__(self, "description", self.description.strip())
        if not isinstance(self.payload, Mapping):
            raise ContractValidationError("payload debe ser un objeto clave-valor")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "sensor_id": self.sensor_id,
            "observed_at": self.observed_at.isoformat().replace("+00:00", "Z"),
            "evidence_type": self.evidence_type,
            "confidence": self.confidence,
            "description": self.description,
            "payload": dict(self.payload),
        }
