"""Repositorios en memoria para probar el MVP sin infraestructura externa."""
from __future__ import annotations

from typing import Protocol, TypeVar

from multisensor.contracts import Evidence, Event, Incident, Observation


T = TypeVar("T")


class RepositoryError(ValueError):
    """Indica una operación inválida sobre un repositorio."""


class ObservationRepository(Protocol):
    def save(self, observation: Observation) -> Observation: ...
    def get(self, observation_id: str) -> Observation | None: ...
    def all(self) -> tuple[Observation, ...]: ...


class EventRepository(Protocol):
    def save(self, event: Event) -> Event: ...
    def get(self, event_id: str) -> Event | None: ...
    def all(self) -> tuple[Event, ...]: ...


class EvidenceRepository(Protocol):
    def save(self, evidence: Evidence) -> Evidence: ...
    def get(self, evidence_id: str) -> Evidence | None: ...
    def all(self) -> tuple[Evidence, ...]: ...


class IncidentRepository(Protocol):
    def save(self, incident: Incident) -> Incident: ...
    def get(self, incident_id: str) -> Incident | None: ...
    def all(self) -> tuple[Incident, ...]: ...


class _MemoryRepository:
    entity_name = "entidad"

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def _save(self, identifier: str, item: T) -> T:
        if identifier in self._items:
            raise RepositoryError(f"{self.entity_name} duplicada: {identifier}")
        self._items[identifier] = item
        return item

    def _get(self, identifier: str) -> T | None:
        return self._items.get(identifier)

    def _all(self) -> tuple[T, ...]:
        return tuple(self._items.values())


class InMemoryObservationRepository(_MemoryRepository, ObservationRepository):
    entity_name = "observación"

    def save(self, observation: Observation) -> Observation:
        if not isinstance(observation, Observation):
            raise RepositoryError("se requiere Observation")
        return self._save(observation.id, observation)

    def get(self, observation_id: str) -> Observation | None:
        return self._get(observation_id)

    def all(self) -> tuple[Observation, ...]:
        return self._all()


class InMemoryEventRepository(_MemoryRepository, EventRepository):
    entity_name = "evento"

    def save(self, event: Event) -> Event:
        if not isinstance(event, Event):
            raise RepositoryError("se requiere Event")
        return self._save(event.id, event)

    def get(self, event_id: str) -> Event | None:
        return self._get(event_id)

    def all(self) -> tuple[Event, ...]:
        return self._all()


class InMemoryEvidenceRepository(_MemoryRepository, EvidenceRepository):
    entity_name = "evidencia"

    def save(self, evidence: Evidence) -> Evidence:
        if not isinstance(evidence, Evidence):
            raise RepositoryError("se requiere Evidence")
        return self._save(evidence.id, evidence)

    def get(self, evidence_id: str) -> Evidence | None:
        return self._get(evidence_id)

    def all(self) -> tuple[Evidence, ...]:
        return self._all()


class InMemoryIncidentRepository(_MemoryRepository, IncidentRepository):
    entity_name = "incidente"

    def save(self, incident: Incident) -> Incident:
        if not isinstance(incident, Incident):
            raise RepositoryError("se requiere Incident")
        return self._save(incident.id, incident)

    def get(self, incident_id: str) -> Incident | None:
        return self._get(incident_id)

    def all(self) -> tuple[Incident, ...]:
        return self._all()
