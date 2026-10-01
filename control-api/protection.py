"""Modelos de dominio para la configuración y el estado de protección."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


SiteType = Literal["property", "farm", "land", "warehouse", "business"]
ProtectionMode = Literal["quiet", "balanced", "strict"]
IntegrationStatus = Literal["configured", "reachable", "unavailable", "not_verified"]


class ProtectionProfile(BaseModel):
    """Configuración única que expresa las preferencias de protección del usuario."""

    model_config = ConfigDict(extra="forbid")

    site_type: SiteType = "property"
    protection_mode: ProtectionMode = "balanced"
    detect_people: StrictBool = True
    detect_vehicles: StrictBool = True
    detect_animals: StrictBool = False
    night_protection: StrictBool = True
    notify_on_suspicious: StrictBool = True
    notify_on_incident: StrictBool = True
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_quiet_hour(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("el horario debe tener formato HH:MM")
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("el horario debe tener formato HH:MM") from exc
        if parsed.strftime("%H:%M") != value:
            raise ValueError("el horario debe tener formato HH:MM")
        return value

    @model_validator(mode="after")
    def validate_quiet_hours_range(self) -> "ProtectionProfile":
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError("quiet_hours_start y quiet_hours_end deben indicarse juntos")
        if self.quiet_hours_start is not None and self.quiet_hours_start == self.quiet_hours_end:
            raise ValueError("quiet_hours_start y quiet_hours_end no pueden ser iguales")
        return self


class DiscoveredCamera(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    enabled: bool


class DiscoveredZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    camera_id: str
    name: str


class DiscoveredNotificationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    class_name: str
    enabled: bool


class CameraResources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    truncated: bool
    active_count: int = Field(ge=0)
    items: list[DiscoveredCamera]


class ZoneResources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    truncated: bool
    items: list[DiscoveredZone]


class NotificationRuleResources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    truncated: bool
    active_count: int = Field(ge=0)
    items: list[DiscoveredNotificationRule]


class IntegrationDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IntegrationStatus
    reason: str = Field(min_length=1)


class ProtectionDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resources: dict[str, CameraResources | ZoneResources | NotificationRuleResources]
    integrations: dict[str, IntegrationDiscovery]

    @model_validator(mode="after")
    def validate_resource_keys(self) -> "ProtectionDiscoveryResponse":
        expected = {"cameras", "zones", "notification_rules"}
        if set(self.resources) != expected:
            raise ValueError("resources debe contener cámaras, zonas y reglas de aviso")
        if set(self.integrations) != {"frigate", "mqtt"}:
            raise ValueError("integrations debe contener Frigate y MQTT")
        return self


def protection_profile_from_row(row: Mapping[str, Any]) -> ProtectionProfile:
    """Construye el perfil de dominio desde la representación SQLite existente."""

    return ProtectionProfile(
        site_type=row["site_type"],
        protection_mode=row["protection_mode"],
        detect_people=bool(row["detect_people"]),
        detect_vehicles=bool(row["detect_vehicles"]),
        detect_animals=bool(row["detect_animals"]),
        night_protection=bool(row["night_protection"]),
        notify_on_suspicious=bool(row["notify_on_suspicious"]),
        notify_on_incident=bool(row["notify_on_incident"]),
        quiet_hours_start=row["quiet_hours_start"],
        quiet_hours_end=row["quiet_hours_end"],
    )
