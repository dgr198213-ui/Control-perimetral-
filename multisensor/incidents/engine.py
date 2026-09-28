"""Motor de incidentes separado de políticas y notificaciones."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from datetime import datetime, timezone

from multisensor.contracts import Event, Incident, Location
from multisensor.fusion import EvidenceBundle


@dataclass(frozen=True, slots=True)
class IncidentPolicy:
    """Reglas mínimas y configurables para convertir evidencia en incidente."""

    minimum_independent_sensors: int = 3
    minimum_confidence: float = 0.5
    incident_type: str = "possible_intrusion"

    def __post_init__(self) -> None:
        if self.minimum_independent_sensors < 2:
            raise ValueError("minimum_independent_sensors debe ser al menos 2")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence debe estar entre 0 y 1")
        if not self.incident_type.strip():
            raise ValueError("incident_type no puede estar vacío")


class IncidentEngine:
    """Convierte EvidenceBundle elegibles en Incident, sin notificar."""

    def __init__(self, policy: IncidentPolicy | None = None) -> None:
        self.policy = policy or IncidentPolicy()
        self._issued: set[str] = set()

    def evaluate(
        self,
        bundle: EvidenceBundle,
        event: Event,
        *,
        location: Location | None = None,
    ) -> Incident | None:
        sensor_count = len({evidence.payload.get("sensor_type") for evidence in bundle.evidences})
        if not bundle.candidate_for_incident:
            return None
        if sensor_count < self.policy.minimum_independent_sensors:
            return None
        if bundle.score < self.policy.minimum_confidence:
            return None
        evidence_ids = tuple(evidence.id for evidence in bundle.evidences)
        digest = sha256("|".join(sorted(evidence_ids)).encode("utf-8")).hexdigest()[:16]
        incident_id = f"incident:{digest}"
        if incident_id in self._issued:
            return None
        observed_times = [evidence.observed_at.astimezone(timezone.utc) for evidence in bundle.evidences]
        started_at = min(observed_times)
        updated_at = max(observed_times)
        window_seconds = float(event.payload.get("temporal_span_seconds", 0.0))
        payload = {
            "source_event_id": event.id,
            "sensor_count": sensor_count,
            "window_seconds": window_seconds,
            "evidence": [evidence.evidence_type for evidence in bundle.evidences],
            "policy": {
                "minimum_independent_sensors": self.policy.minimum_independent_sensors,
                "minimum_confidence": self.policy.minimum_confidence,
            },
        }
        incident = Incident(
            id=incident_id,
            incident_type=self.policy.incident_type,
            started_at=started_at,
            updated_at=updated_at,
            evidence_ids=evidence_ids,
            confidence=bundle.score,
            location=location or event.location,
            status="open",
            explanation=bundle.explanation,
            payload=payload,
        )
        self._issued.add(incident.id)
        return incident
