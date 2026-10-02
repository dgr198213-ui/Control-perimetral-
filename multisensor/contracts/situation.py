"""Contrato canónico para situaciones derivadas de eventos correlacionados."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .observation import ContractValidationError, Location, _confidence, _required_text


@dataclass(frozen=True, slots=True)
class Situation:
    """Interpretación orientada al usuario de un evento, sin crear incidentes."""

    id: str
    situation_type: str
    started_at: datetime
    updated_at: datetime
    confidence: float
    observation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    location: Location | None = None
    status: str = "active"
    explanation: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required_text(self.id, "id"))
        object.__setattr__(self, "situation_type", _required_text(self.situation_type, "situation_type"))
        object.__setattr__(self, "status", _required_text(self.status, "status"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))

        for field_name in ("started_at", "updated_at"):
            value = getattr(self, field_name)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ContractValidationError(f"{field_name} debe incluir zona horaria")
            object.__setattr__(self, field_name, value.astimezone(timezone.utc))
        if self.updated_at < self.started_at:
            raise ContractValidationError("updated_at no puede ser anterior a started_at")

        for field_name, item_name in (("observation_ids", "observation_id"), ("evidence_ids", "evidence_id")):
            raw_ids = getattr(self, field_name)
            if not isinstance(raw_ids, tuple):
                raise ContractValidationError(f"{field_name} debe ser una tupla")
            normalized_ids = tuple(_required_text(item, item_name) for item in raw_ids)
            if len(set(normalized_ids)) != len(normalized_ids):
                raise ContractValidationError(f"{field_name} no puede contener duplicados")
            object.__setattr__(self, field_name, normalized_ids)

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
            "situation_type": self.situation_type,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z"),
            "confidence": self.confidence,
            "observation_ids": list(self.observation_ids),
            "evidence_ids": list(self.evidence_ids),
            "location": self.location.to_dict() if self.location else None,
            "status": self.status,
            "explanation": self.explanation,
            "payload": dict(self.payload),
        }
