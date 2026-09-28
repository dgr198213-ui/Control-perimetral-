"""Persistencia intercambiable del MVP multisensor."""

from .repositories import (
    EventRepository,
    EvidenceRepository,
    InMemoryEventRepository,
    InMemoryEvidenceRepository,
    InMemoryIncidentRepository,
    InMemoryObservationRepository,
    IncidentRepository,
    ObservationRepository,
    RepositoryError,
)

__all__ = [
    "EventRepository",
    "EvidenceRepository",
    "IncidentRepository",
    "InMemoryEventRepository",
    "InMemoryEvidenceRepository",
    "InMemoryIncidentRepository",
    "InMemoryObservationRepository",
    "ObservationRepository",
    "RepositoryError",
]
