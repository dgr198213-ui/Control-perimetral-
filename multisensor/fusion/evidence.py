"""Construcción de evidencia auditable a partir de correlaciones."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multisensor.contracts import Evidence, Observation
from multisensor.correlation import Correlation

from .confidence import ConfidenceBreakdown, score_observation


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Evidencias y score de una correlación, sin crear todavía un incidente."""

    event_id: str
    evidences: tuple[Evidence, ...]
    score: float
    candidate_for_incident: bool
    explanation: str


def build_evidence_bundle(
    correlation: Correlation,
    observations: list[Observation],
    *,
    sensor_reliability: dict[str, float] | None = None,
    candidate_sensor_count: int = 3,
) -> EvidenceBundle:
    """Construye una evidencia por sensor y decide si hay candidato a incidente."""
    by_id = {item.id: item for item in observations}
    selected = [by_id[item_id] for item_id in correlation.observation_ids if item_id in by_id]
    if len(selected) != len(correlation.observation_ids):
        missing = set(correlation.observation_ids) - set(by_id)
        raise ValueError(f"faltan observaciones para crear evidencia: {sorted(missing)}")
    reliability = sensor_reliability or {"camera": 1.0, "pir": 0.9, "wifi_csi": 0.8}
    temporal_factor = correlation.temporal_factor
    spatial_factor = correlation.spatial_factor
    evidences: list[Evidence] = []
    breakdowns: list[ConfidenceBreakdown] = []
    for observation in selected:
        breakdown = score_observation(
            observation,
            temporal_factor=temporal_factor,
            spatial_factor=spatial_factor,
            sensor_reliability=reliability.get(observation.sensor_type, 0.7),
        )
        breakdowns.append(breakdown)
        evidence_id = f"evidence:{correlation.event.id}:{observation.id}"
        payload: dict[str, Any] = {
            "observation_id": observation.id,
            "sensor_type": observation.sensor_type,
            "sensor_confidence": breakdown.sensor_confidence,
            "temporal_factor": breakdown.temporal_factor,
            "spatial_factor": breakdown.spatial_factor,
            "sensor_reliability": breakdown.sensor_reliability,
            "score_rule": "sensor_confidence * temporal_factor * spatial_factor * sensor_reliability",
        }
        evidences.append(
            Evidence(
                id=evidence_id,
                event_id=correlation.event.id,
                sensor_id=observation.sensor_id,
                observed_at=observation.timestamp,
                evidence_type=observation.event_type,
                confidence=breakdown.score,
                description=f"{observation.sensor_type} reportó {observation.event_type}",
                payload=payload,
            )
        )

    score = correlation.event.confidence
    sensor_types = sorted({item.sensor_type for item in selected})
    candidate = len(sensor_types) >= candidate_sensor_count
    explanation = (
        f"{len(sensor_types)} sensores independientes correlacionados en "
        f"{correlation.temporal_span_seconds:.3f} s; score {score:.3f}."
    )
    return EvidenceBundle(
        event_id=correlation.event.id,
        evidences=tuple(evidences),
        score=score,
        candidate_for_incident=candidate,
        explanation=explanation,
    )
