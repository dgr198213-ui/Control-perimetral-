"""Fusión explicable de observaciones correlacionadas."""

from .confidence import ConfidenceBreakdown, score_observation, weighted_fusion_score
from .engine import FusionEngine
from .evidence import EvidenceBundle, build_evidence_bundle

__all__ = [
    "ConfidenceBreakdown",
    "EvidenceBundle",
    "FusionEngine",
    "build_evidence_bundle",
    "score_observation",
    "weighted_fusion_score",
]
