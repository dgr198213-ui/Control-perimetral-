from __future__ import annotations

import json
from pathlib import Path

from multisensor.api.app import create_app
from multisensor.persistence import InMemoryObservationRepository


ANCHORS = [
    {"id": "sensor_a", "x": 0, "y": 0},
    {"id": "sensor_b", "x": 10, "y": 0},
    {"id": "sensor_c", "x": 0, "y": 10},
]


def compliant_app(tmp_path: Path, **kwargs):
    compliance = tmp_path / "compliance"
    compliance.mkdir(exist_ok=True)
    (compliance / "carteleria-verificada").write_text("verified")
    (compliance / "encargo-tratamiento-firmado").write_text("not_applicable")
    return create_app(observations=InMemoryObservationRepository(), compliance_dir=compliance, testing=True, **kwargs)


def test_wifi_csi_ingest_requires_compliance_and_persists_minimal_position(tmp_path: Path) -> None:
    compliance = tmp_path / "compliance"
    compliance.mkdir()
    repository = InMemoryObservationRepository()
    app = create_app(observations=repository, compliance_dir=compliance, testing=True)
    client = app.test_client()
    payload = {"sensor_id": "wifi-csi-01", "timestamp": "2026-10-01T20:00:00Z", "position": {"x": 12.4, "y": 8.7}, "confidence": 0.82}
    assert client.post("/api/multisensor/wifi-csi", json=payload).status_code == 403
    (compliance / "carteleria-verificada").write_text("verified")
    (compliance / "encargo-tratamiento-firmado").write_text("not_applicable")
    response = client.post("/api/multisensor/wifi-csi", json=payload)
    assert response.status_code == 201
    assert response.json["payload"]["position"] == {"x": 12.4, "y": 8.7}
    assert len(repository.all()) == 1


def test_wifi_csi_ingest_triangulates_using_configured_anchors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WIFI_CSI_ANCHORS", json.dumps(ANCHORS))
    app = compliant_app(tmp_path)
    response = app.test_client().post(
        "/api/multisensor/wifi-csi",
        json={"sensor_id": "wifi-csi-01", "timestamp": "2026-10-01T20:00:00Z", "measurements": {"sensor_a": 5, "sensor_b": 5, "sensor_c": 5}, "confidence": 0.82},
    )
    assert response.status_code == 201
    assert response.json["payload"]["position"] == {"x": 5.0, "y": 5.0}


def test_wifi_csi_ingest_rejects_device_identifiers(tmp_path: Path) -> None:
    app = compliant_app(tmp_path)
    response = app.test_client().post(
        "/api/multisensor/wifi-csi",
        json={"sensor_id": "wifi-csi-01", "timestamp": "2026-10-01T20:00:00Z", "bssid": "AA:BB:CC:DD:EE:FF", "position": {"x": 1, "y": 2}, "confidence": 0.8},
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_wifi_csi"
