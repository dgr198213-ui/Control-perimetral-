"""Motor puro para interpretar eventos como situaciones orientadas al usuario."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from multisensor.contracts import Event, Situation


@dataclass(frozen=True, slots=True)
class SituationPolicy:
    """Regla determinista de clasificación de eventos en situaciones."""

    suspicious_confidence_threshold: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.suspicious_confidence_threshold, bool) or not isinstance(
            self.suspicious_confidence_threshold, (int, float)
        ):
            raise ValueError("suspicious_confidence_threshold debe ser un número entre 0 y 1")
        if not 0.0 <= float(self.suspicious_confidence_threshold) <= 1.0:
            raise ValueError("suspicious_confidence_threshold debe estar entre 0 y 1")
        object.__setattr__(self, "suspicious_confidence_threshold", float(self.suspicious_confidence_threshold))


@dataclass(frozen=True, slots=True)
class SituationDecision:
    """Resultado explicable de la evaluación de un evento, sin efectos externos."""

    situation: Situation | None
    reason: str


class SituationEngine:
    """Convierte Event en Situation y evita emitir la misma situación dos veces."""

    def __init__(self, policy: SituationPolicy | None = None) -> None:
        self.policy = policy or SituationPolicy()
        self._issued: set[str] = set()

    def evaluate(self, event: Event) -> SituationDecision:
        """Clasifica un evento usando la confianza ya calculada por correlación."""

        digest = sha256(event.id.encode("utf-8")).hexdigest()[:16]
        situation_id = f"situation:{digest}"
        if situation_id in self._issued:
            return SituationDecision(situation=None, reason="duplicate_event")

        suspicious = event.confidence >= self.policy.suspicious_confidence_threshold
        situation_type = "suspicious_activity" if suspicious else "activity_detected"
        explanation = (
            "Actividad sospechosa detectada mediante evidencia correlacionada."
            if suspicious
            else "Actividad relevante detectada; todavía no alcanza el umbral de actividad sospechosa."
        )
        situation = Situation(
            id=situation_id,
            situation_type=situation_type,
            started_at=event.timestamp,
            updated_at=event.timestamp,
            confidence=event.confidence,
            observation_ids=event.observation_ids,
            location=event.location,
            status="active",
            explanation=explanation,
            payload={
                "source_event_id": event.id,
                "source_event_type": event.event_type,
                "classification": situation_type,
                "policy": {
                    "suspicious_confidence_threshold": self.policy.suspicious_confidence_threshold,
                },
            },
        )
        self._issued.add(situation.id)
        return SituationDecision(situation=situation, reason="classified")
