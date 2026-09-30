from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
from app import create_app  # noqa: E402


KEY = Fernet.generate_key().decode()


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(db_path=tmp_path / "control.sqlite3", encryption_key=KEY, testing=True)
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
