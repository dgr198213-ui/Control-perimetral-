"""Pruebas de salud de sensores."""
from datetime import datetime, timedelta, timezone

import pytest

from multisensor.contracts import Observation
from multisensor.health import SensorHealthService


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def observation(sensor_id: str, sensor_type: str, timestamp: datetime) -> Observation:
    return Observation(
        id=f"{sensor_id}:{timestamp.isoformat()}",
        sensor_id=sensor_id,
        sensor_type=sensor_type,
        timestamp=timestamp,
        event_type="motion",
        confidence=0.8,
    )


def test_sensor_health_distinguishes_recent_and_stale_sources() -> None:
    service = SensorHealthService(stale_after=timedelta(minutes=5))
    result = service.evaluate(
        [
            observation("camera-front", "camera", NOW - timedelta(seconds=30)),
            observation("pir-garden", "pir", NOW - timedelta(minutes=10)),
        ],
        now=NOW,
    )

    assert [item.status for item in result] == ["healthy", "stale"]
    assert result[1].reason == "No hay observaciones recientes."


def test_sensor_health_requires_positive_threshold() -> None:
    with pytest.raises(ValueError, match="positivo"):
        SensorHealthService(stale_after=timedelta(0))
