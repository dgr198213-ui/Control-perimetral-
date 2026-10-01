from __future__ import annotations

import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
from app import create_app  # noqa: E402


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
