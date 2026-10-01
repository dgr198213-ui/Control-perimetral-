"""Persistencia intercambiable del MVP multisensor."""

from .sqlite import SQLiteDomainRepository, SQLiteObservationRepository
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
    "SQLiteDomainRepository",
    "SQLiteObservationRepository",
]
