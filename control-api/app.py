from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from db import Database, utc_now

SESSION_COOKIE = "perimetral_session"
SESSION_TTL_HOURS = 12
PASSWORDS = PasswordHasher()
LOGIN_FAILURES: dict[str, list[float]] = {}


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=256)


class SettingUpdate(BaseModel):
    value: str = Field(max_length=10000)


class CameraInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=554, ge=1, le=65535)
    path: str = Field(min_length=1, max_length=500)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)
    transport: str = Field(default="rtsp", pattern="^rtsp$")
    enabled: bool = True


class CameraUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=554, ge=1, le=65535)
    path: str = Field(min_length=1, max_length=500)
    username: str = Field(min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    transport: str = Field(default="rtsp", pattern="^rtsp$")
    enabled: bool = True


class ZoneInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    coordinates: list[float] = Field(min_length=6, max_length=200)


class RuleInput(BaseModel):
    class_name: str = Field(min_length=1, max_length=50)
    zone_id: str | None = None
    cooldown_seconds: int = Field(default=60, ge=0, le=86400)
    silence_start: str | None = None
    silence_end: str | None = None
    enabled: bool = True


class ComplianceView(BaseModel):
    signage_confirmed: bool
    mandate_confirmed: bool
    kill_switch: bool
    recording_allowed: bool
    updated_at: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def make_fernet(key: str | None) -> Fernet:
    if not key:
        raise HTTPException(status_code=503, detail="CONTROL_API_ENCRYPTION_KEY no configurada")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="CONTROL_API_ENCRYPTION_KEY no válida") from exc


def create_app(
    *,
    db_path: str | Path | None = None,
    encryption_key: str | None = None,
    testing: bool = False,
) -> FastAPI:
    app = FastAPI(title="Control Perimetral API", version="2.0.0")
    app.state.db = Database(db_path or os.getenv("CONTROL_API_DB", "data/control-api.sqlite3"))
    app.state.encryption_key = encryption_key or os.getenv("CONTROL_API_ENCRYPTION_KEY")
    app.state.testing = testing

    def current_user(request: Request, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> Any:
        if not session:
            raise HTTPException(status_code=401, detail="Autenticación requerida")
        db: Database = request.app.state.db
        row = db.one(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
            (hash_token(session), utc_now()),
        )
        if row is None:
            raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
        return row

    def require_compliance(request: Request) -> sqlite3.Row:
        db: Database = request.app.state.db
        row = db.one("SELECT * FROM compliance WHERE id = 1")
        if row is None or not (row["signage_confirmed"] and row["mandate_confirmed"]) or row["kill_switch"]:
            raise HTTPException(status_code=423, detail="Operación bloqueada por cumplimiento")
        return row

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/setup", status_code=201)
    def setup_user(credentials: Credentials, request: Request) -> dict[str, Any]:
        db: Database = request.app.state.db
        if db.one("SELECT id FROM users LIMIT 1") is not None:
            raise HTTPException(status_code=409, detail="El usuario inicial ya está configurado")
        user_id = db.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            (credentials.username.strip(), PASSWORDS.hash(credentials.password), utc_now()),
        ).lastrowid
        db.audit("create", "user", str(user_id), {"username": credentials.username.strip()})
        return {"id": user_id, "username": credentials.username.strip()}

    @app.post("/api/auth/login")
    def login(credentials: Credentials, request: Request, response: Response) -> dict[str, str]:
        db: Database = request.app.state.db
        now = time.time()
        ip = request.client.host if request.client else "unknown"
        failures = [stamp for stamp in LOGIN_FAILURES.get(ip, []) if now - stamp < 60]
        LOGIN_FAILURES[ip] = failures
        row = db.one("SELECT * FROM users WHERE username = ?", (credentials.username.strip(),))
        valid = False
        if row is not None:
            try:
                valid = PASSWORDS.verify(row["password_hash"], credentials.password)
            except VerifyMismatchError:
                valid = False
        if not valid:
            failures.append(now)
            LOGIN_FAILURES[ip] = failures
            if len(failures) >= 5:
                raise HTTPException(status_code=429, detail="Demasiados intentos; espera un minuto")
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
        db.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (hash_token(token), row["id"], expires.isoformat(), utc_now()),
        )
        db.audit("login", "session", None, {"user_id": row["id"]})
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=SESSION_TTL_HOURS * 3600,
            httponly=True,
            secure=not request.app.state.testing,
            samesite="strict",
        )
        return {"status": "ok"}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
        user = current_user(request, session)
        if session:
            request.app.state.db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(session),))
        request.app.state.db.audit("logout", "session", None, {"user_id": user["id"]})
        response.delete_cookie(SESSION_COOKIE)
        return {"status": "ok"}

    @app.get("/api/settings")
    def get_settings(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        rows = request.app.state.db.many("SELECT key, value, updated_at FROM settings ORDER BY key")
        return {"items": [row_dict(row) for row in rows]}

    @app.put("/api/settings/{key}")
    def set_setting(key: str, body: SettingUpdate, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        db.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, body.value, utc_now()),
        )
        db.audit("upsert", "setting", key, {"user_id": user["id"]})
        return {"key": key, "value": body.value}

    @app.get("/api/compliance", response_model=ComplianceView)
    def get_compliance(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        row = request.app.state.db.one("SELECT * FROM compliance WHERE id = 1")
        return {**row_dict(row), "recording_allowed": bool(row["signage_confirmed"] and row["mandate_confirmed"] and not row["kill_switch"])}

    @app.get("/api/cameras")
    def list_cameras(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        rows = request.app.state.db.many("SELECT id, name, host, port, path, username, transport, enabled, created_at, updated_at FROM cameras ORDER BY name")
        return {"items": [row_dict(row) for row in rows]}

    @app.post("/api/cameras", status_code=201)
    def create_camera(body: CameraInput, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        camera_id = str(uuid4())
        now = utc_now()
        db.execute(
            "INSERT INTO cameras(id, name, host, port, path, username, transport, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (camera_id, body.name.strip(), body.host.strip(), body.port, body.path, body.username, body.transport, int(body.enabled), now, now),
        )
        store_secret(db, request, f"camera:{camera_id}:password", body.password, user["id"])
        db.audit("create", "camera", camera_id, {"user_id": user["id"], "name": body.name.strip()})
        return camera_public(db.one("SELECT * FROM cameras WHERE id = ?", (camera_id,)))

    @app.get("/api/cameras/{camera_id}")
    def get_camera(camera_id: str, request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        row = request.app.state.db.one("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        return camera_public(row)

    @app.put("/api/cameras/{camera_id}")
    def update_camera(camera_id: str, body: CameraUpdate, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        if db.one("SELECT id FROM cameras WHERE id = ?", (camera_id,)) is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        db.execute(
            "UPDATE cameras SET name=?, host=?, port=?, path=?, username=?, transport=?, enabled=?, updated_at=? WHERE id=?",
            (body.name.strip(), body.host.strip(), body.port, body.path, body.username, body.transport, int(body.enabled), utc_now(), camera_id),
        )
        if body.password is not None:
            store_secret(db, request, f"camera:{camera_id}:password", body.password, user["id"])
        db.audit("update", "camera", camera_id, {"user_id": user["id"]})
        return camera_public(db.one("SELECT * FROM cameras WHERE id = ?", (camera_id,)))

    @app.delete("/api/cameras/{camera_id}")
    def delete_camera(camera_id: str, request: Request, user: Any = Depends(current_user)) -> dict[str, str]:
        db: Database = request.app.state.db
        if db.one("SELECT id FROM cameras WHERE id = ?", (camera_id,)) is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        db.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        db.audit("delete", "camera", camera_id, {"user_id": user["id"]})
        return {"status": "deleted"}

    @app.post("/api/cameras/{camera_id}/zones", status_code=201)
    def create_zone(camera_id: str, body: ZoneInput, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        if db.one("SELECT id FROM cameras WHERE id = ?", (camera_id,)) is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        zone_id = str(uuid4())
        db.execute(
            "INSERT INTO zones(id, camera_id, name, coordinates, created_at) VALUES (?, ?, ?, ?, ?)",
            (zone_id, camera_id, body.name.strip(), json.dumps(body.coordinates), utc_now()),
        )
        db.audit("create", "zone", zone_id, {"user_id": user["id"], "camera_id": camera_id})
        return zone_public(db.one("SELECT * FROM zones WHERE id = ?", (zone_id,)))

    @app.get("/api/cameras/{camera_id}/zones")
    def list_zones(camera_id: str, request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        rows = request.app.state.db.many("SELECT * FROM zones WHERE camera_id = ? ORDER BY name", (camera_id,))
        return {"items": [zone_public(row) for row in rows]}

    @app.delete("/api/cameras/{camera_id}/zones/{zone_id}")
    def delete_zone(camera_id: str, zone_id: str, request: Request, user: Any = Depends(current_user)) -> dict[str, str]:
        db: Database = request.app.state.db
        if db.one("SELECT id FROM zones WHERE id = ? AND camera_id = ?", (zone_id, camera_id)) is None:
            raise HTTPException(status_code=404, detail="Zona no encontrada")
        db.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
        db.audit("delete", "zone", zone_id, {"user_id": user["id"], "camera_id": camera_id})
        return {"status": "deleted"}

    @app.get("/api/notification-rules")
    def list_rules(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        rows = request.app.state.db.many("SELECT * FROM notification_rules ORDER BY id")
        return {"items": [row_dict(row) for row in rows]}

    @app.post("/api/notification-rules", status_code=201)
    def create_rule(body: RuleInput, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        rule_id = str(uuid4())
        db.execute(
            "INSERT INTO notification_rules(id, class_name, zone_id, cooldown_seconds, silence_start, silence_end, enabled) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rule_id, body.class_name, body.zone_id, body.cooldown_seconds, body.silence_start, body.silence_end, int(body.enabled)),
        )
        db.audit("create", "notification_rule", rule_id, {"user_id": user["id"]})
        return row_dict(db.one("SELECT * FROM notification_rules WHERE id = ?", (rule_id,)))

    @app.post("/api/secrets/{name}", status_code=201)
    def set_secret(name: str, value: SettingUpdate, request: Request, user: Any = Depends(current_user)) -> dict[str, str]:
        store_secret(request.app.state.db, request, name, value.value, user["id"])
        return {"name": name, "status": "stored"}

    @app.get("/api/secrets")
    def list_secrets(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        rows = request.app.state.db.many("SELECT name, created_at, updated_at FROM secrets ORDER BY name")
        return {"items": [row_dict(row) for row in rows]}

    @app.get("/api/audit")
    def audit_log(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        rows = request.app.state.db.many("SELECT id, action, entity, entity_id, details, created_at FROM audit_log ORDER BY id")
        return {"items": [row_dict(row) for row in rows]}

    @app.post("/api/frigate/render")
    def render_frigate(request: Request, _user: Any = Depends(current_user)) -> dict[str, str]:
        db: Database = request.app.state.db
        compliance = db.one("SELECT * FROM compliance WHERE id = 1")
        allowed = bool(compliance["signage_confirmed"] and compliance["mandate_confirmed"] and not compliance["kill_switch"])
        cameras = db.many("SELECT * FROM cameras WHERE enabled = 1 ORDER BY id")
        config: dict[str, Any] = {
            "mqtt": {"host": "mosquitto", "port": 1883},
            "objects": {"track": ["person", "car", "motorcycle", "bicycle"]},
            "record": {"enabled": allowed},
            "snapshots": {"enabled": allowed},
            "cameras": {},
        }
        for camera in cameras:
            zones = db.many("SELECT * FROM zones WHERE camera_id = ? ORDER BY name", (camera["id"],))
            config["cameras"][camera["name"]] = {
                "ffmpeg": {"inputs": [{"path": f"{camera['transport']}://{camera['host']}:{camera['port']}/{camera['path'].lstrip('/')}", "roles": ["detect"]}]},
                "zones": {zone["name"]: {"coordinates": ",".join(map(str, json.loads(zone["coordinates"]))), "objects": ["person", "car", "motorcycle", "bicycle"]} for zone in zones},
            }
        return {"yaml": yaml.safe_dump(config, sort_keys=False), "recording_enabled": str(allowed).lower()}

    return app


def store_secret(db: Database, request: Request, name: str, value: str, user_id: int) -> None:
    cipher = make_fernet(request.app.state.encryption_key).encrypt(value.encode("utf-8"))
    now = utc_now()
    db.execute(
        "INSERT INTO secrets(name, ciphertext, created_at, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET ciphertext=excluded.ciphertext, updated_at=excluded.updated_at",
        (name, cipher, now, now),
    )
    db.audit("upsert", "secret", name, {"user_id": user_id})


def camera_public(row: Any) -> dict[str, Any]:
    result = row_dict(row)
    result.pop("password", None)
    return result


def zone_public(row: Any) -> dict[str, Any]:
    result = row_dict(row)
    if "coordinates" in result:
        result["coordinates"] = json.loads(result["coordinates"])
    return result


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
