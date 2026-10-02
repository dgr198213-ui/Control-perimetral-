"""Evaluación determinista de salud y frescura de sensores."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from multisensor.contracts import Observation


@dataclass(frozen=True, slots=True)
class SensorHealth:
    sensor_id: str
    sensor_type: str
    status: str
    last_seen: datetime | None
    age_seconds: float | None
    observation_count: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "status": self.status,
            "last_seen": self.last_seen.isoformat().replace("+00:00", "Z") if self.last_seen else None,
            "age_seconds": self.age_seconds,
            "observation_count": self.observation_count,
            "reason": self.reason,
        }


class SensorHealthService:
    """Calcula salud sin acceder a red ni modificar repositorios."""

    def __init__(self, *, stale_after: timedelta = timedelta(minutes=5)) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after debe ser positivo")
        self.stale_after = stale_after

    def evaluate(self, observations: Iterable[Observation], *, now: datetime | None = None) -> tuple[SensorHealth, ...]:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        grouped: dict[str, list[Observation]] = {}
        for observation in observations:
            grouped.setdefault(observation.sensor_id, []).append(observation)
        result: list[SensorHealth] = []
        for sensor_id, items in sorted(grouped.items()):
            latest = max(item.timestamp.astimezone(timezone.utc) for item in items)
            age = max(0.0, (current - latest).total_seconds())
            stale = age > self.stale_after.total_seconds()
            result.append(
                SensorHealth(
                    sensor_id=sensor_id,
                    sensor_type=items[0].sensor_type,
                    status="stale" if stale else "healthy",
                    last_seen=latest,
                    age_seconds=age,
                    observation_count=len(items),
                    reason=("No hay observaciones recientes." if stale else "El sensor ha producido observaciones recientes."),
                )
            )
        return tuple(result)
