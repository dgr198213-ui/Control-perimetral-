"""Contrato canónico para incidentes formados a partir de evidencia correlacionada."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .observation import ContractValidationError, Location, _confidence, _required_text


@dataclass(frozen=True, slots=True)
class Incident:
    """Conclusión auditable basada en una o más evidencias.

    El motor de incidentes llegará en una fase posterior. Este contrato solo
    define el formato necesario para explicar cualquier conclusión futura.
    """

    id: str
    incident_type: str
    started_at: datetime
    updated_at: datetime
    evidence_ids: tuple[str, ...]
    confidence: float
    location: Location | None = None
    status: str = "open"
    explanation: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required_text(self.id, "id"))
        object.__setattr__(self, "incident_type", _required_text(self.incident_type, "incident_type"))
        object.__setattr__(self, "status", _required_text(self.status, "status"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))

        for field_name in ("started_at", "updated_at"):
            value = getattr(self, field_name)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ContractValidationError(f"{field_name} debe incluir zona horaria")
            object.__setattr__(self, field_name, value.astimezone(timezone.utc))
        if self.updated_at < self.started_at:
            raise ContractValidationError("updated_at no puede ser anterior a started_at")

        if not self.evidence_ids:
            raise ContractValidationError("evidence_ids debe incluir al menos una evidencia")
        normalized_ids = tuple(_required_text(item, "evidence_id") for item in self.evidence_ids)
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ContractValidationError("evidence_ids no puede contener duplicados")
        object.__setattr__(self, "evidence_ids", normalized_ids)

        if self.location is not None and not isinstance(self.location, Location):
            raise ContractValidationError("location debe ser Location o None")
        if not isinstance(self.explanation, str):
            raise ContractValidationError("explanation debe ser texto")
        object.__setattr__(self, "explanation", self.explanation.strip())
        if not isinstance(self.payload, Mapping):
            raise ContractValidationError("payload debe ser un objeto clave-valor")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_type": self.incident_type,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z"),
            "evidence_ids": list(self.evidence_ids),
            "confidence": self.confidence,
            "location": self.location.to_dict() if self.location else None,
            "status": self.status,
            "explanation": self.explanation,
            "payload": dict(self.payload),
        }
