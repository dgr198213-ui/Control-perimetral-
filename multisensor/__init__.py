"""Contratos canónicos y normalización para sensores del perímetro.

Este paquete no conecta todavía sensores ni altera el flujo Frigate/MQTT/notifier.
"""

from .contracts import Evidence, Event, Incident, Location, Observation
from .normalization import NormalizationError, normalize_observation
from .privacy import PrivacyViolation, PublicResourcePolicy, sanitize_public_resource, validate_wifi_csi_payload

__all__ = [
    "Evidence",
    "Event",
    "Incident",
    "Location",
    "NormalizationError",
    "Observation",
    "normalize_observation",
    "PrivacyViolation",
    "PublicResourcePolicy",
    "sanitize_public_resource",
    "validate_wifi_csi_payload",
]
