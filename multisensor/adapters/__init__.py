"""Adaptadores de fuentes externas al núcleo multisensor."""

from .frigate import FrigateAdapterError, frigate_event_to_observation

__all__ = ["FrigateAdapterError", "frigate_event_to_observation"]
