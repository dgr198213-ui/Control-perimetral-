from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIGRATIONS = (
    (
        1,
        "wp2-core",
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE secrets (
            name TEXT PRIMARY KEY,
            ciphertext BLOB NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE cameras (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 554,
            path TEXT NOT NULL,
            username TEXT NOT NULL,
            transport TEXT NOT NULL DEFAULT 'rtsp',
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE zones (
            id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            coordinates TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE notification_rules (
            id TEXT PRIMARY KEY,
            class_name TEXT NOT NULL,
            zone_id TEXT,
            cooldown_seconds INTEGER NOT NULL DEFAULT 60,
            silence_start TEXT,
            silence_end TEXT,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            FOREIGN KEY(zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );
        CREATE TABLE compliance (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            signage_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (signage_confirmed IN (0, 1)),
            mandate_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (mandate_confirmed IN (0, 1)),
            kill_switch INTEGER NOT NULL DEFAULT 0 CHECK (kill_switch IN (0, 1)),
            updated_at TEXT NOT NULL
        );
        INSERT INTO compliance(id, updated_at) VALUES (1, datetime('now'));
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id TEXT,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TRIGGER audit_log_no_update
        BEFORE UPDATE ON audit_log BEGIN
            SELECT RAISE(ABORT, 'audit_log es inmutable');
        END;
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log BEGIN
            SELECT RAISE(ABORT, 'audit_log es inmutable');
        END;
        """,
    ),
    (
        2,
        "user-centered-protection",
        """
        CREATE TABLE protection_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            site_type TEXT NOT NULL DEFAULT 'property'
                CHECK (site_type IN ('property', 'farm', 'land', 'warehouse', 'business')),
            protection_mode TEXT NOT NULL DEFAULT 'balanced'
                CHECK (protection_mode IN ('quiet', 'balanced', 'strict')),
            detect_people INTEGER NOT NULL DEFAULT 1 CHECK (detect_people IN (0, 1)),
            detect_vehicles INTEGER NOT NULL DEFAULT 1 CHECK (detect_vehicles IN (0, 1)),
            detect_animals INTEGER NOT NULL DEFAULT 0 CHECK (detect_animals IN (0, 1)),
            night_protection INTEGER NOT NULL DEFAULT 1 CHECK (night_protection IN (0, 1)),
            notify_on_suspicious INTEGER NOT NULL DEFAULT 1 CHECK (notify_on_suspicious IN (0, 1)),
            notify_on_incident INTEGER NOT NULL DEFAULT 1 CHECK (notify_on_incident IN (0, 1)),
            quiet_hours_start TEXT,
            quiet_hours_end TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO protection_profile(id, created_at, updated_at)
        VALUES (1, datetime('now'), datetime('now'));
        """,
    ),
    (
        3,
        "multi-tenant-isolation",
        """
        CREATE TABLE tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO tenants(id, slug, name, created_at)
        VALUES (1, 'default', 'Organización principal', datetime('now'));

        ALTER TABLE users ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE cameras ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE zones ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE notification_rules ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE audit_log ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;

        CREATE TABLE settings_v3 (
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, key)
        );
        INSERT INTO settings_v3(tenant_id, key, value, updated_at)
        SELECT 1, key, value, updated_at FROM settings;
        DROP TABLE settings;
        ALTER TABLE settings_v3 RENAME TO settings;

        CREATE TABLE secrets_v3 (
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            ciphertext BLOB NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, name)
        );
        INSERT INTO secrets_v3(tenant_id, name, ciphertext, created_at, updated_at)
        SELECT 1, name, ciphertext, created_at, updated_at FROM secrets;
        DROP TABLE secrets;
        ALTER TABLE secrets_v3 RENAME TO secrets;

        CREATE TABLE compliance_v3 (
            id INTEGER NOT NULL UNIQUE,
            tenant_id INTEGER PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            signage_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (signage_confirmed IN (0, 1)),
            mandate_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (mandate_confirmed IN (0, 1)),
            kill_switch INTEGER NOT NULL DEFAULT 0 CHECK (kill_switch IN (0, 1)),
            updated_at TEXT NOT NULL
        );
        INSERT INTO compliance_v3(id, tenant_id, signage_confirmed, mandate_confirmed, kill_switch, updated_at)
        SELECT 1, 1, signage_confirmed, mandate_confirmed, kill_switch, updated_at FROM compliance;
        DROP TABLE compliance;
        ALTER TABLE compliance_v3 RENAME TO compliance;

        CREATE TABLE protection_profile_v3 (
            tenant_id INTEGER PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            site_type TEXT NOT NULL DEFAULT 'property'
                CHECK (site_type IN ('property', 'farm', 'land', 'warehouse', 'business')),
            protection_mode TEXT NOT NULL DEFAULT 'balanced'
                CHECK (protection_mode IN ('quiet', 'balanced', 'strict')),
            detect_people INTEGER NOT NULL DEFAULT 1 CHECK (detect_people IN (0, 1)),
            detect_vehicles INTEGER NOT NULL DEFAULT 1 CHECK (detect_vehicles IN (0, 1)),
            detect_animals INTEGER NOT NULL DEFAULT 0 CHECK (detect_animals IN (0, 1)),
            night_protection INTEGER NOT NULL DEFAULT 1 CHECK (night_protection IN (0, 1)),
            notify_on_suspicious INTEGER NOT NULL DEFAULT 1 CHECK (notify_on_suspicious IN (0, 1)),
            notify_on_incident INTEGER NOT NULL DEFAULT 1 CHECK (notify_on_incident IN (0, 1)),
            quiet_hours_start TEXT,
            quiet_hours_end TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO protection_profile_v3(tenant_id, site_type, protection_mode, detect_people, detect_vehicles,
            detect_animals, night_protection, notify_on_suspicious, notify_on_incident,
            quiet_hours_start, quiet_hours_end, created_at, updated_at)
        SELECT 1, site_type, protection_mode, detect_people, detect_vehicles, detect_animals,
            night_protection, notify_on_suspicious, notify_on_incident,
            quiet_hours_start, quiet_hours_end, created_at, updated_at FROM protection_profile;
        DROP TABLE protection_profile;
        ALTER TABLE protection_profile_v3 RENAME TO protection_profile;
        """,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path = "data/control-api.sqlite3") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def migrate(self) -> None:
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        applied = {row[0] for row in self.connection.execute("SELECT version FROM schema_migrations")}
        for version, name, sql in MIGRATIONS:
            if version in applied:
                continue
            with self.connection:
                self.connection.executescript(sql)
                self.connection.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, utc_now()),
                )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self.connection.execute(sql, params).fetchone()

    def many(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(sql, params).fetchall())

    def audit(self, action: str, entity: str, entity_id: str | None, details: dict[str, Any]) -> None:
        tenant_id = int(details.get("tenant_id", 1))
        self.execute(
            "INSERT INTO audit_log(tenant_id, action, entity, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, action, entity, entity_id, json.dumps(details, sort_keys=True), utc_now()),
        )
