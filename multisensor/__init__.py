"""Contratos canónicos y normalización para sensores del perímetro.

Este paquete no conecta todavía sensores ni altera el flujo Frigate/MQTT/notifier.
"""

from .contracts import Evidence, Event, Incident, Location, Observation
from .normalization import NormalizationError, normalize_observation

__all__ = [
    "Evidence",
    "Event",
    "Incident",
    "Location",
    "NormalizationError",
    "Observation",
    "normalize_observation",
]
