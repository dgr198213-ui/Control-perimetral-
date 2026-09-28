"""Adaptadores de fuentes externas al núcleo multisensor."""

from typing import Any, Mapping

from .frigate import FrigateAdapterError, frigate_event_to_observation
from .pir import PirAdapterError, pir_message_to_observation


def message_to_observation(sensor_type: str, message: Mapping[str, Any]):
    """Despacha un mensaje de sensor al adaptador canónico correspondiente."""
    if not isinstance(sensor_type, str) or not sensor_type.strip():
        raise ValueError("sensor_type debe ser texto no vacío")
    normalized_type = sensor_type.strip().lower()
    if normalized_type in {"frigate", "camera"}:
        return frigate_event_to_observation(message)
    if normalized_type == "pir":
        return pir_message_to_observation(message)
    raise ValueError(f"Tipo de sensor no soportado: {sensor_type}")


__all__ = [
    "FrigateAdapterError",
    "PirAdapterError",
    "frigate_event_to_observation",
    "message_to_observation",
    "pir_message_to_observation",
]
