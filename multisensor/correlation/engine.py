"""Correlación temporal y espacial de observaciones multisensor."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import combinations
from math import asin, cos, radians, sin, sqrt
from typing import Iterable, Mapping

from multisensor.contracts import Event, Location, Observation


class CorrelationError(ValueError):
    """Indica que no se puede evaluar una correlación multisensor."""


@dataclass(frozen=True, slots=True)
class CorrelationConfig:
    """Parámetros explícitos y revisables del motor."""

    temporal_window: timedelta = timedelta(seconds=5)
    max_distance_m: float = 75.0
    min_sensor_types: int = 2
    sensor_reliability: Mapping[str, float] = field(
        default_factory=lambda: {
            "camera": 1.0,
            "pir": 0.9,
            "wifi_csi": 0.8,
        }
    )
    unknown_location_factor: float = 0.75

    def __post_init__(self) -> None:
        if self.temporal_window <= timedelta(0):
            raise CorrelationError("temporal_window debe ser positiva")
        if self.max_distance_m <= 0:
            raise CorrelationError("max_distance_m debe ser positiva")
        if self.min_sensor_types < 2:
            raise CorrelationError("min_sensor_types debe ser al menos 2")
        if not 0.0 < self.unknown_location_factor <= 1.0:
            raise CorrelationError("unknown_location_factor debe estar entre 0 y 1")
        for sensor_type, reliability in self.sensor_reliability.items():
            if not 0.0 < reliability <= 1.0:
                raise CorrelationError(f"fiabilidad inválida para {sensor_type}")


@dataclass(frozen=True, slots=True)
class Correlation:
    """Resultado auditable de una correlación; no es todavía un incidente."""

    event: Event
    observation_ids: tuple[str, ...]
    sensor_types: tuple[str, ...]
    temporal_span_seconds: float
    spatial_factor: float
    temporal_factor: float


def _haversine_m(first: Location, second: Location) -> float:
    earth_radius_m = 6_371_000.0
    lat_delta = radians(second.latitude - first.latitude)
    lon_delta = radians(second.longitude - first.longitude)
    lat_first = radians(first.latitude)
    lat_second = radians(second.latitude)
    a = sin(lat_delta / 2) ** 2 + cos(lat_first) * cos(lat_second) * sin(lon_delta / 2) ** 2
    return 2 * earth_radius_m * asin(sqrt(a))


def _is_positive_observation(observation: Observation) -> bool:
    if observation.event_type.endswith("_cleared"):
        return False
    if observation.payload.get("motion") is False:
        return False
    return observation.confidence > 0.0


class TemporalSpatialCorrelator:
    """Ventana acotada que combina señales sin emitir alertas ni incidentes.

    Cada nueva observación se compara con las observaciones recientes. Se
    conserva como máximo la señal de mayor confianza por tipo de sensor, se
    exige diversidad de sensores y se calcula una confianza explicable:

    ``evidence_weight × temporal_factor × spatial_factor × reliability_factor``.
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self.config = config or CorrelationConfig()
        self._recent: list[Observation] = []
        self._emitted_keys: set[tuple[str, ...]] = set()

    @property
    def recent_observation_ids(self) -> tuple[str, ...]:
        return tuple(observation.id for observation in self._recent)

    def ingest(self, observation: Observation) -> Correlation | None:
        """Añade una observación y devuelve una correlación si es suficiente."""
        if not isinstance(observation, Observation):
            raise CorrelationError("observation debe ser Observation")
        if not _is_positive_observation(observation):
            return None

        self._recent = [
            item
            for item in self._recent
            if abs((observation.timestamp - item.timestamp).total_seconds())
            <= self.config.temporal_window.total_seconds()
        ]
        if any(item.id == observation.id for item in self._recent):
            return None
        self._recent.append(observation)

        selected = self._select_best_per_sensor(self._recent, observation.timestamp)
        if len({item.sensor_type for item in selected}) < self.config.min_sensor_types:
            return None
        try:
            return self._build_correlation(selected)
        except CorrelationError:
            self._recent = [item for item in self._recent if item.id != observation.id]
            raise

    def correlate(self, observations: Iterable[Observation]) -> Correlation | None:
        """Evalúa un conjunto finito con las mismas reglas que el flujo online."""
        items = list(observations)
        if not items:
            return None
        if any(not isinstance(item, Observation) for item in items):
            raise CorrelationError("todas las entradas deben ser Observation")
        selected = self._select_best_per_sensor(items, max(item.timestamp for item in items))
        if len({item.sensor_type for item in selected}) < self.config.min_sensor_types:
            return None
        return self._build_correlation(selected)

    def _select_best_per_sensor(
        self, observations: Iterable[Observation], reference_time: datetime
    ) -> list[Observation]:
        candidates = [
            item
            for item in observations
            if _is_positive_observation(item)
            and abs((reference_time - item.timestamp).total_seconds())
            <= self.config.temporal_window.total_seconds()
        ]
        selected: dict[str, Observation] = {}
        for item in candidates:
            current = selected.get(item.sensor_type)
            if current is None or (item.confidence, item.timestamp) > (current.confidence, current.timestamp):
                selected[item.sensor_type] = item
        return list(selected.values())

    def _build_correlation(self, observations: list[Observation]) -> Correlation | None:
        if len(observations) < self.config.min_sensor_types:
            return None
        ids = tuple(sorted(item.id for item in observations))
        if ids in self._emitted_keys:
            return None

        timestamps = [item.timestamp.astimezone(timezone.utc) for item in observations]
        span_seconds = (max(timestamps) - min(timestamps)).total_seconds()
        temporal_factor = max(
            0.0,
            1.0 - span_seconds / self.config.temporal_window.total_seconds(),
        )
        spatial_factor, distance_details = self._spatial_factor(observations)
        reliability_values = [
            self.config.sensor_reliability.get(item.sensor_type, 0.7) for item in observations
        ]
        reliability_total = sum(reliability_values)
        evidence_weight = sum(
            item.confidence * reliability
            for item, reliability in zip(observations, reliability_values)
        ) / reliability_total
        reliability_factor = sum(reliability_values) / len(reliability_values)
        confidence = max(
            0.0,
            min(1.0, evidence_weight * temporal_factor * spatial_factor * reliability_factor),
        )

        location = self._representative_location(observations)
        payload = {
            "observation_ids": list(ids),
            "sensor_types": sorted(item.sensor_type for item in observations),
            "temporal_span_seconds": round(span_seconds, 6),
            "temporal_factor": round(temporal_factor, 6),
            "spatial_factor": round(spatial_factor, 6),
            "spatial_distances_m": distance_details,
            "evidence_weight": round(evidence_weight, 6),
            "reliability_factor": round(reliability_factor, 6),
            "rule": "evidence_weight * temporal_factor * spatial_factor * reliability_factor",
        }
        digest = sha256("|".join(ids).encode("utf-8")).hexdigest()[:16]
        event = Event(
            id=f"correlation:{digest}",
            event_type="multisensor_motion",
            timestamp=max(timestamps),
            observation_ids=ids,
            confidence=confidence,
            location=location,
            payload=payload,
            source="temporal-spatial-correlator",
        )
        self._emitted_keys.add(ids)
        return Correlation(
            event=event,
            observation_ids=ids,
            sensor_types=tuple(sorted(item.sensor_type for item in observations)),
            temporal_span_seconds=span_seconds,
            spatial_factor=spatial_factor,
            temporal_factor=temporal_factor,
        )

    def _spatial_factor(self, observations: list[Observation]) -> tuple[float, dict[str, float]]:
        located = [item for item in observations if item.location is not None]
        missing_count = len(observations) - len(located)
        distances: dict[str, float] = {}
        known_factors: list[float] = []
        for first, second in combinations(located, 2):
            distance = _haversine_m(first.location, second.location)
            pair_key = f"{first.id}|{second.id}"
            distances[pair_key] = round(distance, 3)
            if distance > self.config.max_distance_m:
                raise CorrelationError(
                    f"observaciones espacialmente incompatibles: {pair_key} ({distance:.1f} m)"
                )
            known_factors.append(max(0.0, 1.0 - distance / self.config.max_distance_m))

        if known_factors:
            factor = sum(known_factors) / len(known_factors)
        else:
            factor = self.config.unknown_location_factor
        if missing_count:
            factor *= self.config.unknown_location_factor
        return factor, distances

    @staticmethod
    def _representative_location(observations: list[Observation]) -> Location | None:
        located = [item.location for item in observations if item.location is not None]
        if not located:
            return None
        return Location(
            latitude=sum(item.latitude for item in located) / len(located),
            longitude=sum(item.longitude for item in located) / len(located),
        )
