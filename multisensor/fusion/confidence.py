"""Cálculo explicable de confianza para la fusión multisensor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from multisensor.contracts import Observation


@dataclass(frozen=True, slots=True)
class ConfidenceBreakdown:
    """Componentes del score final para auditoría y explicación."""

    sensor_confidence: float
    temporal_factor: float
    spatial_factor: float
    sensor_reliability: float
    score: float


def score_observation(
    observation: Observation,
    *,
    temporal_factor: float,
    spatial_factor: float,
    sensor_reliability: float,
) -> ConfidenceBreakdown:
    """Calcula ``confidence × temporal × spatial × reliability`` acotado a 0..1."""
    factors = {
        "temporal_factor": temporal_factor,
        "spatial_factor": spatial_factor,
        "sensor_reliability": sensor_reliability,
    }
    if any(not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0 for value in factors.values()):
        raise ValueError("los factores de confianza deben estar entre 0 y 1")
    score = observation.confidence * temporal_factor * spatial_factor * sensor_reliability
    return ConfidenceBreakdown(
        sensor_confidence=observation.confidence,
        temporal_factor=float(temporal_factor),
        spatial_factor=float(spatial_factor),
        sensor_reliability=float(sensor_reliability),
        score=max(0.0, min(1.0, float(score))),
    )


def weighted_fusion_score(
    observations: list[Observation],
    *,
    temporal_factor: float,
    spatial_factor: float,
    sensor_reliability: Mapping[str, float],
) -> float:
    """Combina sensores independientes sin sumar sus confianzas."""
    if not observations:
        raise ValueError("se requiere al menos una observación")
    weights = [sensor_reliability.get(item.sensor_type, 0.7) for item in observations]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("la fiabilidad total debe ser positiva")
    evidence_weight = sum(item.confidence * weight for item, weight in zip(observations, weights)) / total_weight
    reliability_factor = sum(weights) / len(weights)
    score = evidence_weight * temporal_factor * spatial_factor * reliability_factor
    return max(0.0, min(1.0, float(score)))
