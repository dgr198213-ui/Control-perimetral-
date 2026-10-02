"""Pruebas HTTP de integración de la API multisensor."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import unittest

from multisensor.api import create_app
from multisensor.contracts import Event, Incident, Observation
from multisensor.persistence import (
    InMemoryEventRepository,
    InMemoryIncidentRepository,
    InMemoryObservationRepository,
)


UTC = timezone.utc


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compliance_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.compliance_dir)
        for marker in ("carteleria-verificada", "encargo-tratamiento-firmado"):
            (self.compliance_dir / marker).touch()
        self.observations = InMemoryObservationRepository()
        self.events = InMemoryEventRepository()
        self.incidents = InMemoryIncidentRepository()
        self.observation = Observation(
            id="obs:1",
            sensor_id="pir-front",
            sensor_type="pir",
            timestamp=datetime(2026, 9, 28, 19, 20, tzinfo=UTC),
            event_type="motion",
            confidence=0.9,
            payload={"motion": True},
            source="pir",
        )
        self.observations.save(self.observation)
        self.events.save(
            Event(
                id="event:1",
                event_type="multisensor_motion",
                timestamp=self.observation.timestamp,
                observation_ids=(self.observation.id,),
                confidence=0.8,
                payload={"temporal_span_seconds": 1.2},
            )
        )
        self.incidents.save(
            Incident(
                id="incident:1",
                incident_type="possible_intrusion",
                started_at=self.observation.timestamp,
                updated_at=self.observation.timestamp,
                evidence_ids=("evidence:1",),
                confidence=0.8,
                explanation="Tres señales independientes.",
            )
        )
        self.client = create_app(
            observations=self.observations,
            events=self.events,
            incidents=self.incidents,
            compliance_dir=self.compliance_dir,
        ).test_client()

    def test_missing_compliance_blocks_every_read_endpoint(self) -> None:
        blocked_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, blocked_dir)
        client = create_app(compliance_dir=blocked_dir).test_client()
        for path in (
            "/api/multisensor/observations",
            "/api/multisensor/observations/obs:1",
            "/api/multisensor/events",
            "/api/multisensor/events/event:1",
            "/api/multisensor/incidents",
            "/api/multisensor/incidents/incident:1",
            "/api/multisensor/sensors",
            "/api/multisensor/health",
        ):
            response = client.get(path)
            self.assertEqual(response.status_code, 403, path)
            self.assertEqual(response.json["error"]["code"], "compliance_blocked")

    def test_collections_and_resource_endpoints_return_contracts(self) -> None:
        for path, key in (
            ("/api/multisensor/observations", "id"),
            ("/api/multisensor/events", "id"),
            ("/api/multisensor/incidents", "id"),
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["count"], 1)
            self.assertIn(key, response.json["items"][0])

        observation_response = self.client.get("/api/multisensor/observations/obs:1")
        event_response = self.client.get("/api/multisensor/events/event:1")
        incident_response = self.client.get("/api/multisensor/incidents/incident:1")
        self.assertEqual(observation_response.status_code, 200)
        self.assertEqual(event_response.json["observation_ids"], ["obs:1"])
        self.assertEqual(incident_response.json["evidence_ids"], ["evidence:1"])

    def test_health_endpoint_reports_sensor_freshness(self) -> None:
        response = self.client.get("/api/multisensor/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertEqual(response.json["items"][0]["sensor_id"], "pir-front")
        self.assertEqual(response.json["items"][0]["status"], "stale")

    def test_sensors_endpoint_is_derived_from_observations(self) -> None:
        response = self.client.get("/api/multisensor/sensors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["items"][0]["sensor_id"], "pir-front")
        self.assertEqual(response.json["items"][0]["observation_count"], 1)
        self.assertEqual(response.json["items"][0]["last_seen"], "2026-09-28T19:20:00Z")

    def test_unknown_resource_is_404_and_invalid_limit_is_400(self) -> None:
        not_found = self.client.get("/api/multisensor/incidents/missing")
        invalid_limit = self.client.get("/api/multisensor/observations?limit=zero")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(not_found.json["error"]["code"], "not_found")
        self.assertEqual(invalid_limit.status_code, 400)
        self.assertEqual(invalid_limit.json["error"]["code"], "bad_request")

    def test_unhandled_repository_failure_returns_500(self) -> None:
        class BrokenRepository:
            def all(self):
                raise RuntimeError("backend failure")

        client = create_app(
            observations=BrokenRepository(), compliance_dir=self.compliance_dir
        ).test_client()
        response = client.get("/api/multisensor/observations")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["error"]["code"], "internal_error")


if __name__ == "__main__":
    unittest.main()
