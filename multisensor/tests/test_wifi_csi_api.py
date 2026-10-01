from __future__ import annotations

from pathlib import Path

from multisensor.api.app import create_app
from multisensor.persistence import InMemoryObservationRepository


def test_wifi_csi_ingest_requires_compliance_and_persists_aggregate(tmp_path: Path) -> None:
    compliance = tmp_path / "compliance"
    compliance.mkdir()
    repository = InMemoryObservationRepository()
    app = create_app(observations=repository, compliance_dir=compliance, testing=True)
    client = app.test_client()
    payload = {
        "sensor_id": "wifi-csi-01",
        "timestamp": "2026-10-01T20:00:00Z",
        "event_type": "human_motion",
        "confidence": 0.82,
        "features": {"motion_score": 0.73, "window_ms": 1000},
    }
    blocked = client.post("/api/multisensor/wifi-csi", json=payload)
    assert blocked.status_code == 403

    (compliance / "carteleria-verificada").write_text("verified")
    (compliance / "encargo-tratamiento-firmado").write_text("not_applicable")
    response = client.post("/api/multisensor/wifi-csi", json=payload)
    assert response.status_code == 201
    assert response.json["sensor_type"] == "wifi_csi"
    assert len(repository.all()) == 1


def test_wifi_csi_ingest_rejects_device_identifiers(tmp_path: Path) -> None:
    compliance = tmp_path / "compliance"
    compliance.mkdir()
    (compliance / "carteleria-verificada").write_text("verified")
    (compliance / "encargo-tratamiento-firmado").write_text("not_applicable")
    app = create_app(observations=InMemoryObservationRepository(), compliance_dir=compliance, testing=True)
    response = app.test_client().post(
        "/api/multisensor/wifi-csi",
        json={
            "sensor_id": "wifi-csi-01",
            "timestamp": "2026-10-01T20:00:00Z",
            "confidence": 0.8,
            "bssid": "AA:BB:CC:DD:EE:FF",
            "features": {"motion_score": 0.7},
        },
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_wifi_csi"
