from __future__ import annotations

import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
import app as control_api_app  # noqa: E402
from app import create_app, probe_frigate, probe_mqtt  # noqa: E402


KEY = Fernet.generate_key().decode()


def make_client(tmp_path: Path, frigate_restart: Callable[[], None] | None = None) -> TestClient:
    app = create_app(
        db_path=tmp_path / "control.sqlite3",
        encryption_key=KEY,
        frigate_config_path=tmp_path / "frigate-config" / "config.yml",
        frigate_restart=frigate_restart or (lambda: None),
        testing=True,
    )
    return TestClient(app)


def authenticated_client(tmp_path: Path) -> TestClient:
    client = make_client(tmp_path)
    setup = client.post("/api/auth/setup", json={"username": "demo", "password": "una-password-larga"})
    assert setup.status_code == 201
    login = client.post("/api/auth/login", json={"username": "demo", "password": "una-password-larga"})
    assert login.status_code == 200
    return client


def test_health_is_public_and_auth_is_required(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/cameras").status_code == 401


def test_metrics_exposes_prometheus_request_counter(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.get("/api/health")
    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'control_api_requests_total{method="GET",path="/api/health",status="200"}' in response.text


def test_single_user_setup_and_login_cookie(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.post("/api/auth/setup", json={"username": "demo", "password": "una-password-larga"}).status_code == 201
    assert client.post("/api/auth/setup", json={"username": "otro", "password": "otra-password-larga"}).status_code == 409
    assert client.post("/api/auth/login", json={"username": "demo", "password": "incorrecta-larga"}).status_code == 401
    login = client.post("/api/auth/login", json={"username": "demo", "password": "una-password-larga"})
    assert login.status_code == 200
    cookie = login.cookies.get("perimetral_session")
    assert cookie
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]


def test_camera_zone_secret_and_rendering_never_return_password(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    created = client.post(
        "/api/cameras",
        json={
            "name": "demo-camara",
            "host": "192.0.2.10",
            "port": 554,
            "path": "stream",
            "username": "demo",
            "password": "no-debe-salir",
        },
    )
    assert created.status_code == 201
    camera = created.json()
    assert camera["host"] == "192.0.2.10"
    assert "password" not in camera
    camera_id = camera["id"]
    secret_list = client.get("/api/secrets")
    assert secret_list.status_code == 200
    assert "no-debe-salir" not in secret_list.text
    zone = client.post(f"/api/cameras/{camera_id}/zones", json={"name": "perimetro", "coordinates": [0, 0, 1, 0, 1, 1]})
    assert zone.status_code == 201
    rendered = client.post("/api/frigate/render")
    assert rendered.status_code == 200
    assert "no-debe-salir" not in rendered.text
    assert "192.0.2.10" in rendered.json()["yaml"]


def test_render_writes_generated_config_and_restarts_frigate(tmp_path: Path) -> None:
    restarts: list[str] = []
    client = make_client(tmp_path, frigate_restart=lambda: restarts.append("requested"))
    setup = client.post("/api/auth/setup", json={"username": "demo", "password": "una-password-larga"})
    assert setup.status_code == 201
    assert client.post("/api/auth/login", json={"username": "demo", "password": "una-password-larga"}).status_code == 200

    response = client.post("/api/frigate/render")

    assert response.status_code == 200
    assert response.json()["applied"] is True
    assert restarts == ["requested"]
    generated = (tmp_path / "frigate-config" / "config.yml").read_text()
    assert generated == response.json()["yaml"]
    assert "version: 0.16-0" in generated
    assert "record:\n  enabled: false" in generated


def test_render_calls_internal_frigate_restart_endpoint(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, float]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, url: str) -> FakeResponse:
            calls.append((url, self.timeout))
            return FakeResponse()

    monkeypatch.setenv("FRIGATE_API_URL", "http://frigate-interno:5000")
    monkeypatch.setattr("app.httpx.Client", FakeClient)
    app = create_app(
        db_path=tmp_path / "control.sqlite3",
        encryption_key=KEY,
        frigate_config_path=tmp_path / "frigate-config" / "config.yml",
        testing=True,
    )
    client = TestClient(app)
    assert client.post("/api/auth/setup", json={"username": "demo", "password": "una-password-larga"}).status_code == 201
    assert client.post("/api/auth/login", json={"username": "demo", "password": "una-password-larga"}).status_code == 200

    response = client.post("/api/frigate/render")

    assert response.status_code == 200
    assert calls == [("http://frigate-interno:5000/api/restart", 10.0)]


def test_render_reports_restart_failure_after_writing_config(tmp_path: Path) -> None:
    def unavailable_frigate() -> None:
        raise httpx.ConnectError("Frigate no disponible")

    client = make_client(tmp_path, frigate_restart=unavailable_frigate)
    setup = client.post("/api/auth/setup", json={"username": "demo", "password": "una-password-larga"})
    assert setup.status_code == 201
    assert client.post("/api/auth/login", json={"username": "demo", "password": "una-password-larga"}).status_code == 200

    response = client.post("/api/frigate/render")

    assert response.status_code == 502
    assert (tmp_path / "frigate-config" / "config.yml").exists()


def test_compliance_is_fail_closed_for_recording_and_audit_is_immutable(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    initial = client.post("/api/frigate/render")
    assert initial.json()["recording_enabled"] == "false"
    compliance = client.get("/api/compliance")
    assert compliance.status_code == 200
    assert compliance.json()["recording_allowed"] is False
    audit = client.get("/api/audit")
    assert audit.status_code == 200
    assert audit.json()["items"]
    connection = sqlite3.connect(tmp_path / "control.sqlite3")
    row_id = connection.execute("SELECT id FROM audit_log LIMIT 1").fetchone()[0]
    try:
        connection.execute("DELETE FROM audit_log WHERE id = ?", (row_id,))
        connection.commit()
    except sqlite3.DatabaseError as exc:
        assert "inmutable" in str(exc)
    else:
        raise AssertionError("audit_log permitió DELETE")
    finally:
        connection.close()


def test_compliance_confirmation_revocation_and_kill_switch_lifecycle(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)

    confirmed = client.post("/api/compliance/confirm", json={"reason": "Revisión documental completada"})
    assert confirmed.status_code == 200
    assert confirmed.json()["recording_allowed"] is True
    assert confirmed.json()["kill_switch"] is False

    revoked = client.post("/api/compliance/revoke", json={"reason": "Se retiró la autorización operativa"})
    assert revoked.status_code == 200
    assert revoked.json()["recording_allowed"] is False
    assert revoked.json()["kill_switch"] is True

    blocked_confirmation = client.post("/api/compliance/confirm", json={"reason": "Intento prematuro"})
    assert blocked_confirmation.status_code == 423

    blocked_clear = client.post("/api/compliance/clear-kill-switch", json={"reason": "No hay confirmaciones"})
    assert blocked_clear.status_code == 423

    connection = sqlite3.connect(tmp_path / "control.sqlite3")
    connection.execute(
        "UPDATE compliance SET signage_confirmed = 1, mandate_confirmed = 1 WHERE id = 1"
    )
    connection.commit()
    connection.close()

    cleared = client.post("/api/compliance/clear-kill-switch", json={"reason": "Nueva revisión autorizada"})
    assert cleared.status_code == 200
    assert cleared.json()["recording_allowed"] is True
    assert cleared.json()["kill_switch"] is False

    audit = client.get("/api/audit").json()["items"]
    assert [entry["action"] for entry in audit[-3:]] == ["confirm", "revoke", "clear_kill_switch"]


def test_frigate_probe_hides_network_details_and_reports_unavailable(monkeypatch) -> None:
    class UnavailableClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            raise httpx.ConnectError("private network detail")

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(control_api_app.httpx, "Client", UnavailableClient)

    result = probe_frigate("http://frigate:5000")

    assert result.status == "unavailable"
    assert "private network" not in result.reason


def test_mqtt_probe_reports_reachable_without_publishing(monkeypatch) -> None:
    calls: list[tuple[str, int, float]] = []

    class ReachableSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_connection(address: tuple[str, int], timeout: float):
        calls.append((address[0], address[1], timeout))
        return ReachableSocket()

    monkeypatch.setattr(control_api_app.socket, "create_connection", fake_connection)

    result = probe_mqtt("mosquitto", 1883)

    assert result.status == "reachable"
    assert calls == [("mosquitto", 1883, 2.0)]


def test_protection_profile_defaults_require_auth_and_are_persistent(tmp_path: Path) -> None:
    anonymous = make_client(tmp_path)
    assert anonymous.get("/api/protection-profile").status_code == 401

    client = authenticated_client(tmp_path)
    profile = client.get("/api/protection-profile")

    assert profile.status_code == 200
    assert profile.json() == {
        "site_type": "property",
        "protection_mode": "balanced",
        "detect_people": True,
        "detect_vehicles": True,
        "detect_animals": False,
        "night_protection": True,
        "notify_on_suspicious": True,
        "notify_on_incident": True,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
    }


def test_protection_profile_updates_and_audits_changes(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    response = client.put(
        "/api/protection-profile",
        json={
            "site_type": "farm",
            "protection_mode": "strict",
            "detect_people": True,
            "detect_vehicles": False,
            "detect_animals": True,
            "night_protection": False,
            "notify_on_suspicious": False,
            "notify_on_incident": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "06:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["site_type"] == "farm"
    assert response.json()["quiet_hours_end"] == "06:00"
    assert client.get("/api/protection-profile").json() == response.json()
    audit = client.get("/api/audit").json()["items"]
    assert audit[-1]["action"] == "update"
    assert audit[-1]["entity"] == "protection_profile"


def test_protection_profile_rejects_invalid_values_and_inconsistent_hours(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    invalid_site = client.put("/api/protection-profile", json={"site_type": "castle"})
    assert invalid_site.status_code == 422

    invalid_boolean = client.put("/api/protection-profile", json={"detect_people": "true"})
    assert invalid_boolean.status_code == 422

    inconsistent_hours = client.put(
        "/api/protection-profile",
        json={"quiet_hours_start": "22:00", "quiet_hours_end": "22:00"},
    )
    assert inconsistent_hours.status_code == 422


def test_protection_status_and_recommendations_use_existing_system_state(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    assert client.get("/api/protection/status").status_code == 200
    assert client.get("/api/protection/recommendations").status_code == 200

    status_response = client.get("/api/protection/status").json()
    recommendations = client.get("/api/protection/recommendations").json()
    assert status_response["status"] == "setup_required"
    assert status_response["capabilities"]["cameras"] is False
    assert status_response["capabilities"]["multisensor_correlation"] is False
    assert "Añade y activa al menos una cámara" in status_response["setup_required"]
    assert {item["code"] for item in recommendations["items"]} == {
        "add_camera",
        "confirm_compliance",
    }


def test_protection_status_reports_attention_for_unzoned_camera(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    assert client.post("/api/compliance/confirm", json={"reason": "Revisión documental completada"}).status_code == 200
    created = client.post(
        "/api/cameras",
        json={
            "name": "entrada",
            "host": "192.0.2.20",
            "path": "stream",
            "username": "demo",
            "password": "secreto-de-prueba",
        },
    )
    assert created.status_code == 201

    status_response = client.get("/api/protection/status").json()
    assert status_response["status"] == "attention"
    assert status_response["capabilities"]["cameras"] is True
    assert status_response["recording_allowed"] is True


def test_protection_discovery_reports_only_persisted_resources(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    unauthenticated = make_client(tmp_path).get("/api/protection/discovery")
    assert unauthenticated.status_code == 401

    empty = client.get("/api/protection/discovery")
    assert empty.status_code == 200
    assert empty.json()["resources"]["cameras"] == {
        "configured": False,
        "count": 0,
        "returned_count": 0,
        "truncated": False,
        "active_count": 0,
        "items": [],
    }
    assert empty.json()["integrations"]["frigate"]["status"] == "not_verified"
    assert empty.json()["integrations"]["mqtt"]["status"] == "not_verified"

    created = client.post(
        "/api/cameras",
        json={
            "name": "entrada",
            "host": "192.0.2.30",
            "path": "stream",
            "username": "demo",
            "password": "secreto-de-prueba",
        },
    )
    assert created.status_code == 201
    camera_id = created.json()["id"]
    zone = client.post(f"/api/cameras/{camera_id}/zones", json={"name": "puerta", "coordinates": [0, 0, 1, 0, 1, 1]})
    assert zone.status_code == 201
    rule = client.post("/api/notification-rules", json={"class_name": "person"})
    assert rule.status_code == 201

    discovery = client.get("/api/protection/discovery").json()
    assert discovery["resources"]["cameras"]["count"] == 1
    assert discovery["resources"]["cameras"]["active_count"] == 1
    assert discovery["resources"]["zones"]["count"] == 1
    assert discovery["resources"]["notification_rules"]["active_count"] == 1
    assert discovery["resources"]["cameras"]["returned_count"] == 1
    assert discovery["resources"]["cameras"]["truncated"] is False
    assert discovery["resources"]["zones"]["returned_count"] == 1
    assert discovery["resources"]["notification_rules"]["returned_count"] == 1
    assert "192.0.2.30" not in client.get("/api/protection/discovery").text
    assert "secreto-de-prueba" not in client.get("/api/protection/discovery").text
    assert "password" not in client.get("/api/protection/discovery").text.lower()


def test_discovery_probes_report_reachable_integrations_without_exposing_endpoints(tmp_path: Path) -> None:
    client = authenticated_client(tmp_path)
    app = client.app

    app.state.testing = False
    app.state.discovery_probe_frigate = lambda _url: {
        "status": "reachable",
        "reason": "Frigate respondió correctamente.",
    }
    app.state.discovery_probe_mqtt = lambda _host, _port: {
        "status": "reachable",
        "reason": "El broker MQTT acepta conexiones TCP.",
    }

    response = client.get("/api/protection/discovery")

    assert response.status_code == 200
    payload = response.json()
    assert payload["integrations"] == {
        "frigate": {"status": "reachable", "reason": "Frigate respondió correctamente."},
        "mqtt": {"status": "reachable", "reason": "El broker MQTT acepta conexiones TCP."},
    }
    assert "http://" not in response.text
    assert "mosquitto" not in response.text


def test_public_sources_catalog_is_authenticated_and_privacy_scoped(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/api/public-sources").status_code == 401
    authenticated = authenticated_client(tmp_path)
    response = authenticated.get("/api/public-sources")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 3
    assert any(item["id"] == "dgt-traffic-cameras" and item["status"] == "integrated" for item in payload["items"])
    assert all(item["personal_tracking"] is False for item in payload["items"])
    assert "TELEGRAM_BOT_TOKEN" not in response.text
    assert "bssid" not in response.text.lower()
