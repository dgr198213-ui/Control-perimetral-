from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import sqlite3
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from uuid import uuid4

import yaml
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from db import Database, utc_now
from protection import (
    CameraResources,
    DiscoveredCamera,
    DiscoveredNotificationRule,
    DiscoveredZone,
    IntegrationDiscovery,
    NotificationRuleResources,
    ProtectionDiscoveryResponse,
    ProtectionProfile,
    ZoneResources,
    protection_profile_from_row,
)

SESSION_COOKIE = "perimetral_session"
SESSION_TTL_HOURS = 12
PASSWORDS = PasswordHasher()
LOGIN_FAILURES: dict[str, list[float]] = {}
DISCOVERY_TIMEOUT_SECONDS = 2.0
MAX_DISCOVERY_ITEMS = 1000


def probe_frigate(base_url: str, *, timeout: float = DISCOVERY_TIMEOUT_SECONDS) -> IntegrationDiscovery:
    """Comprueba el endpoint de versión interno sin devolver detalles de red."""

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url.rstrip('/')}/api/version")
        if response.is_success:
            return IntegrationDiscovery(status="reachable", reason="Frigate respondió correctamente.")
        return IntegrationDiscovery(status="unavailable", reason="Frigate respondió con un estado no válido.")
    except httpx.HTTPError:
        return IntegrationDiscovery(status="unavailable", reason="Frigate no está disponible en este momento.")


def probe_mqtt(host: str, port: int, *, timeout: float = DISCOVERY_TIMEOUT_SECONDS) -> IntegrationDiscovery:
    """Comprueba solo la accesibilidad TCP del broker, sin publicar ni suscribirse."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return IntegrationDiscovery(status="reachable", reason="El broker MQTT acepta conexiones TCP.")
    except (OSError, ValueError):
        return IntegrationDiscovery(status="unavailable", reason="El broker MQTT no está disponible en este momento.")


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


class ComplianceReason(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


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
    frigate_config_path: str | Path | None = None,
    frigate_restart: Callable[[], None] | None = None,
    testing: bool = False,
) -> FastAPI:
    app = FastAPI(title="Control Perimetral API", version="2.0.0")
    app.state.db = Database(db_path or os.getenv("CONTROL_API_DB", "data/control-api.sqlite3"))
    app.state.encryption_key = encryption_key or os.getenv("CONTROL_API_ENCRYPTION_KEY")
    app.state.frigate_config_path = Path(frigate_config_path or os.getenv("FRIGATE_CONFIG_PATH", "/config-generated/config.yml"))
    frigate_api_url = os.getenv("FRIGATE_API_URL", "http://frigate:5000").rstrip("/")
    mqtt_host = os.getenv("MQTT_HOST", "mosquitto")
    try:
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    except ValueError:
        mqtt_port = 1883

    def restart_frigate() -> None:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{frigate_api_url}/api/restart")
            response.raise_for_status()

    app.state.frigate_restart = frigate_restart or restart_frigate
    app.state.discovery_probe_frigate = (
        (lambda _url: IntegrationDiscovery(status="not_verified", reason="Comprobación de red desactivada durante las pruebas."))
        if testing
        else probe_frigate
    )
    app.state.discovery_probe_mqtt = (
        (lambda _host, _port: IntegrationDiscovery(status="not_verified", reason="Comprobación de red desactivada durante las pruebas."))
        if testing
        else probe_mqtt
    )
    app.state.discovery_frigate_url = frigate_api_url
    app.state.discovery_mqtt_host = mqtt_host
    app.state.discovery_mqtt_port = mqtt_port
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

    def current_protection_profile(db: Database) -> ProtectionProfile:
        row = db.one("SELECT * FROM protection_profile WHERE id = 1")
        if row is None:
            raise HTTPException(status_code=500, detail="El perfil de protección no está disponible")
        return protection_profile_from_row(row)

    def protection_status(db: Database) -> dict[str, Any]:
        profile = current_protection_profile(db)
        cameras = db.many("SELECT id FROM cameras WHERE enabled = 1")
        zones = db.many("SELECT id FROM zones")
        notification_rules = db.many("SELECT id FROM notification_rules WHERE enabled = 1")
        compliance = db.one("SELECT * FROM compliance WHERE id = 1")
        recording_allowed = bool(
            compliance
            and compliance["signage_confirmed"]
            and compliance["mandate_confirmed"]
            and not compliance["kill_switch"]
        )

        setup_required: list[str] = []
        if not cameras:
            setup_required.append("Añade y activa al menos una cámara")
        if compliance is None or not compliance["signage_confirmed"] or not compliance["mandate_confirmed"]:
            setup_required.append("Confirma los requisitos de cumplimiento antes de activar la protección")
        elif compliance["kill_switch"]:
            setup_required.append("El interruptor de seguridad está activo")

        attention_required = bool(cameras) and (not zones or (profile.notify_on_suspicious and not notification_rules))
        if setup_required:
            status_value = "setup_required"
            summary = "Completa la configuración necesaria para activar la protección."
        elif attention_required:
            status_value = "attention"
            summary = "La protección está activa, pero conviene completar su configuración."
        else:
            status_value = "protected"
            summary = "La protección está configurada y las fuentes activas pueden vigilar el sitio."

        return {
            "status": status_value,
            "summary": summary,
            "profile": {
                "site_type": profile.site_type,
                "protection_mode": profile.protection_mode,
            },
            "capabilities": {
                "cameras": bool(cameras),
                "motion_detection": bool(cameras),
                "multisensor_correlation": False,
                "notifications": bool(notification_rules),
            },
            "setup_required": setup_required,
            "recording_allowed": recording_allowed,
        }

    @app.get("/api/protection-profile", response_model=ProtectionProfile)
    def get_protection_profile(request: Request, _user: Any = Depends(current_user)) -> ProtectionProfile:
        return current_protection_profile(request.app.state.db)

    @app.put("/api/protection-profile", response_model=ProtectionProfile)
    def update_protection_profile(
        body: ProtectionProfile,
        request: Request,
        user: Any = Depends(current_user),
    ) -> ProtectionProfile:
        db: Database = request.app.state.db
        values = body.model_dump()
        db.execute(
            "UPDATE protection_profile SET site_type=?, protection_mode=?, detect_people=?, "
            "detect_vehicles=?, detect_animals=?, night_protection=?, notify_on_suspicious=?, "
            "notify_on_incident=?, quiet_hours_start=?, quiet_hours_end=?, updated_at=? WHERE id=1",
            (
                values["site_type"],
                values["protection_mode"],
                int(values["detect_people"]),
                int(values["detect_vehicles"]),
                int(values["detect_animals"]),
                int(values["night_protection"]),
                int(values["notify_on_suspicious"]),
                int(values["notify_on_incident"]),
                values["quiet_hours_start"],
                values["quiet_hours_end"],
                utc_now(),
            ),
        )
        db.audit("update", "protection_profile", "1", {"user_id": user["id"]})
        return current_protection_profile(db)

    @app.get("/api/protection/status")
    def get_protection_status(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        return protection_status(request.app.state.db)

    @app.get("/api/protection/discovery", response_model=ProtectionDiscoveryResponse)
    def get_protection_discovery(
        request: Request,
        _user: Any = Depends(current_user),
    ) -> ProtectionDiscoveryResponse:
        db: Database = request.app.state.db
        camera_count = int(db.one("SELECT COUNT(*) AS count FROM cameras")["count"])
        active_camera_count = int(db.one("SELECT COUNT(*) AS count FROM cameras WHERE enabled = 1")["count"])
        zone_count = int(db.one("SELECT COUNT(*) AS count FROM zones")["count"])
        rule_count = int(db.one("SELECT COUNT(*) AS count FROM notification_rules")["count"])
        active_rule_count = int(db.one("SELECT COUNT(*) AS count FROM notification_rules WHERE enabled = 1")["count"])
        cameras = db.many("SELECT id, name, enabled FROM cameras ORDER BY name LIMIT ?", (MAX_DISCOVERY_ITEMS,))
        zones = db.many("SELECT id, camera_id, name FROM zones ORDER BY name LIMIT ?", (MAX_DISCOVERY_ITEMS,))
        rules = db.many("SELECT id, class_name, enabled FROM notification_rules ORDER BY id LIMIT ?", (MAX_DISCOVERY_ITEMS,))
        frigate = request.app.state.discovery_probe_frigate(request.app.state.discovery_frigate_url)
        mqtt = request.app.state.discovery_probe_mqtt(
            request.app.state.discovery_mqtt_host,
            request.app.state.discovery_mqtt_port,
        )
        return ProtectionDiscoveryResponse(
            resources={
                "cameras": CameraResources(
                    configured=camera_count > 0,
                    count=camera_count,
                    returned_count=len(cameras),
                    truncated=camera_count > len(cameras),
                    active_count=active_camera_count,
                    items=[DiscoveredCamera(id=row["id"], name=row["name"], enabled=bool(row["enabled"])) for row in cameras],
                ),
                "zones": ZoneResources(
                    configured=zone_count > 0,
                    count=zone_count,
                    returned_count=len(zones),
                    truncated=zone_count > len(zones),
                    items=[DiscoveredZone(id=row["id"], camera_id=row["camera_id"], name=row["name"]) for row in zones],
                ),
                "notification_rules": NotificationRuleResources(
                    configured=rule_count > 0,
                    count=rule_count,
                    returned_count=len(rules),
                    truncated=rule_count > len(rules),
                    active_count=active_rule_count,
                    items=[DiscoveredNotificationRule(id=row["id"], class_name=row["class_name"], enabled=bool(row["enabled"])) for row in rules],
                ),
            },
            integrations={"frigate": frigate, "mqtt": mqtt},
        )

    @app.get("/api/protection/recommendations")
    def get_protection_recommendations(request: Request, _user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        profile = current_protection_profile(db)
        cameras = db.many("SELECT id FROM cameras")
        enabled_cameras = db.many("SELECT id FROM cameras WHERE enabled = 1")
        zones = db.many("SELECT id FROM zones")
        notification_rules = db.many("SELECT id FROM notification_rules WHERE enabled = 1")
        compliance = db.one("SELECT * FROM compliance WHERE id = 1")
        recommendations: list[dict[str, str]] = []
        if not cameras:
            recommendations.append({"code": "add_camera", "message": "Añade al menos una cámara para iniciar la protección."})
        elif not enabled_cameras:
            recommendations.append({"code": "enable_camera", "message": "Activa al menos una cámara configurada."})
        if enabled_cameras and not zones:
            recommendations.append({"code": "add_zone", "message": "Define al menos una zona de protección para las cámaras activas."})
        if not profile.night_protection:
            recommendations.append({"code": "enable_night_protection", "message": "La protección nocturna está desactivada."})
        if enabled_cameras and profile.notify_on_suspicious and not notification_rules:
            recommendations.append({"code": "add_notification_rule", "message": "Configura una regla de aviso para la actividad sospechosa."})
        if compliance is None or not compliance["signage_confirmed"] or not compliance["mandate_confirmed"]:
            recommendations.append({"code": "confirm_compliance", "message": "Confirma los requisitos de cumplimiento antes de activar la protección."})
        elif compliance["kill_switch"]:
            recommendations.append({"code": "clear_kill_switch", "message": "El interruptor de seguridad está activo; revísalo antes de continuar."})
        return {"items": recommendations}

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

    @app.post("/api/compliance/confirm", response_model=ComplianceView)
    def confirm_compliance(body: ComplianceReason, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        row = db.one("SELECT * FROM compliance WHERE id = 1")
        if row["kill_switch"]:
            raise HTTPException(status_code=423, detail="El kill-switch está activo; libéralo explícitamente antes de confirmar")
        db.execute(
            "UPDATE compliance SET signage_confirmed = 1, mandate_confirmed = 1, updated_at = ? WHERE id = 1",
            (utc_now(),),
        )
        db.audit("confirm", "compliance", "1", {"user_id": user["id"], "reason": body.reason})
        updated = db.one("SELECT * FROM compliance WHERE id = 1")
        return {**row_dict(updated), "recording_allowed": True}

    @app.post("/api/compliance/revoke", response_model=ComplianceView)
    def revoke_compliance(body: ComplianceReason, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        db.execute(
            "UPDATE compliance SET signage_confirmed = 0, mandate_confirmed = 0, kill_switch = 1, updated_at = ? WHERE id = 1",
            (utc_now(),),
        )
        db.audit("revoke", "compliance", "1", {"user_id": user["id"], "reason": body.reason})
        updated = db.one("SELECT * FROM compliance WHERE id = 1")
        return {**row_dict(updated), "recording_allowed": False}

    @app.post("/api/compliance/clear-kill-switch", response_model=ComplianceView)
    def clear_kill_switch(body: ComplianceReason, request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        row = db.one("SELECT * FROM compliance WHERE id = 1")
        if not (row["signage_confirmed"] and row["mandate_confirmed"]):
            raise HTTPException(status_code=423, detail="No se puede liberar el kill-switch sin ambas confirmaciones")
        db.execute("UPDATE compliance SET kill_switch = 0, updated_at = ? WHERE id = 1", (utc_now(),))
        db.audit("clear_kill_switch", "compliance", "1", {"user_id": user["id"], "reason": body.reason})
        updated = db.one("SELECT * FROM compliance WHERE id = 1")
        return {**row_dict(updated), "recording_allowed": True}

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
    def render_frigate(request: Request, user: Any = Depends(current_user)) -> dict[str, Any]:
        db: Database = request.app.state.db
        compliance = db.one("SELECT * FROM compliance WHERE id = 1")
        allowed = bool(compliance["signage_confirmed"] and compliance["mandate_confirmed"] and not compliance["kill_switch"])
        cameras = db.many("SELECT * FROM cameras WHERE enabled = 1 ORDER BY id")
        config: dict[str, Any] = {
            "version": "0.16-0",
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

        rendered_yaml = yaml.safe_dump(config, sort_keys=False)
        config_path: Path = request.app.state.frigate_config_path
        temporary_path = config_path.with_name(f".{config_path.name}.{uuid4().hex}.tmp")
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("w", encoding="utf-8") as generated_file:
                generated_file.write(rendered_yaml)
                generated_file.flush()
                os.fsync(generated_file.fileno())
            os.replace(temporary_path, config_path)
        except OSError as exc:
            temporary_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="No se pudo escribir la configuración de Frigate") from exc

        try:
            request.app.state.frigate_restart()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="La configuración se guardó, pero Frigate no confirmó el reinicio") from exc

        db.audit("apply", "frigate_config", str(config_path), {"user_id": user["id"], "recording_enabled": allowed})
        return {"yaml": rendered_yaml, "recording_enabled": str(allowed).lower(), "applied": True}

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
