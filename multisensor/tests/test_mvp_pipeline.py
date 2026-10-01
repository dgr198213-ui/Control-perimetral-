"""Prueba de extremo a extremo del núcleo MVP, sin broker ni servicios externos."""
from __future__ import annotations

import unittest

from multisensor.adapters import message_to_observation
from multisensor.correlation import TemporalSpatialCorrelator
from multisensor.fusion import FusionEngine
from multisensor.incidents import IncidentEngine
from multisensor.persistence import (
    InMemoryEvidenceRepository,
    InMemoryIncidentRepository,
    InMemoryObservationRepository,
)


class MvpPipelineTests(unittest.TestCase):
    def test_frigate_pir_wifi_flow_reaches_memory_repositories(self) -> None:
        camera = message_to_observation(
            "frigate",
            {
                "type": "new",
                "after": {
                    "id": "frigate-1",
                    "camera": "front",
                    "label": "person",
                    "start_time": 1790623214.0,
                    "top_score": 0.91,
                    "location": {"lat": 43.24, "lon": -5.34},
                },
            },
        )
        pir = message_to_observation(
            "pir",
            {
                "sensor_id": "pir-front",
                "timestamp": 1790623214.0,
                "motion": True,
                "location": {"lat": 43.24, "lon": -5.34},
            },
        )
        wifi = message_to_observation(
            "wifi_csi",
            {
                "sensor_id": "wifi-csi-front",
                "timestamp": 1790623214.0,
                "event_type": "human_motion",
                "confidence": 0.84,
                "features": {"motion_score": 0.72, "phase_variance": 0.61},
                "location": {"lat": 43.24, "lon": -5.34},
            },
        )

        observation_repository = InMemoryObservationRepository()
        for observation in (camera, pir, wifi):
            observation_repository.save(observation)

        correlator = TemporalSpatialCorrelator()
        correlator.ingest(camera)
        correlator.ingest(pir)
        correlation = correlator.ingest(wifi)
        self.assertIsNotNone(correlation)
        assert correlation is not None

        bundle = FusionEngine().fuse(correlation, [camera, pir, wifi])
        evidence_repository = InMemoryEvidenceRepository()
        for evidence in bundle.evidences:
            evidence_repository.save(evidence)

        incident = IncidentEngine().evaluate(bundle, correlation.event)
        self.assertIsNotNone(incident)
        assert incident is not None
        incident_repository = InMemoryIncidentRepository()
        incident_repository.save(incident)

        self.assertEqual(len(observation_repository.all()), 3)
        self.assertEqual(len(evidence_repository.all()), 3)
        self.assertEqual(incident_repository.get(incident.id), incident)
        self.assertEqual(incident.payload["sensor_count"], 3)


if __name__ == "__main__":
    unittest.main()
