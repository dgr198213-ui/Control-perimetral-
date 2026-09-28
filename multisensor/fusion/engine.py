"""Motor de fusión que separa Correlation, Evidence e Incident."""
from __future__ import annotations

from multisensor.contracts import Observation
from multisensor.correlation import Correlation

from .evidence import EvidenceBundle, build_evidence_bundle


class FusionEngine:
    """Genera evidencia explicable a partir de una correlación."""

    def __init__(self, sensor_reliability: dict[str, float] | None = None) -> None:
        self.sensor_reliability = sensor_reliability or {
            "camera": 1.0,
            "pir": 0.9,
            "wifi_csi": 0.8,
        }

    def fuse(self, correlation: Correlation, observations: list[Observation]) -> EvidenceBundle:
        return build_evidence_bundle(
            correlation,
            observations,
            sensor_reliability=self.sensor_reliability,
            candidate_sensor_count=3,
        )
