"""Contexto determinista para explicar situaciones sin afirmar intrusiones."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from multisensor.contracts import Situation


@dataclass(frozen=True, slots=True)
class SituationContext:
    situation_id: str
    time_bucket: str
    zone: str | None
    recent_activity_count: int
    persistence_seconds: float
    interpretation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "situation_id": self.situation_id,
            "time_bucket": self.time_bucket,
            "zone": self.zone,
            "recent_activity_count": self.recent_activity_count,
            "persistence_seconds": self.persistence_seconds,
            "interpretation": self.interpretation,
        }


class ContextEngine:
    """Enriquece una situación con señales contextuales explícitas."""

    def enrich(
        self,
        situation: Situation,
        *,
        zone: str | None = None,
        recent_activity_count: int = 0,
        persistence_seconds: float = 0.0,
    ) -> SituationContext:
        if recent_activity_count < 0 or persistence_seconds < 0:
            raise ValueError("las métricas contextuales no pueden ser negativas")
        hour = situation.started_at.astimezone(timezone.utc).hour
        time_bucket = "night" if hour < 6 or hour >= 22 else "day"
        if situation.situation_type == "suspicious_activity" and time_bucket == "night" and persistence_seconds >= 30:
            interpretation = "Actividad sospechosa persistente durante la noche."
        elif recent_activity_count > 0:
            interpretation = "Actividad relacionada con actividad reciente del sitio."
        else:
            interpretation = "Actividad sin contexto adicional suficiente."
        return SituationContext(
            situation_id=situation.id,
            time_bucket=time_bucket,
            zone=zone,
            recent_activity_count=recent_activity_count,
            persistence_seconds=float(persistence_seconds),
            interpretation=interpretation,
        )
