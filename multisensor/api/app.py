"""API HTTP de solo lectura para el dominio multisensor."""
from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify, request

from multisensor.persistence import (
    EventRepository,
    IncidentRepository,
    InMemoryEventRepository,
    InMemoryIncidentRepository,
    InMemoryObservationRepository,
    ObservationRepository,
)

LOG = logging.getLogger("multisensor-api")
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def _error_payload(code: str, message: str) -> tuple[dict[str, Any], int]:
    return {"error": {"code": code, "message": message}}, 0


def create_app(
    *,
    observations: ObservationRepository | None = None,
    events: EventRepository | None = None,
    incidents: IncidentRepository | None = None,
) -> Flask:
    """Crea una API desacoplada del almacenamiento concreto."""
    observation_repository = observations or InMemoryObservationRepository()
    event_repository = events or InMemoryEventRepository()
    incident_repository = incidents or InMemoryIncidentRepository()
    app = Flask(__name__)

    def limit_value() -> int:
        raw_limit = request.args.get("limit")
        if raw_limit is None:
            return DEFAULT_LIMIT
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise ValueError("limit debe ser un entero positivo") from exc
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit debe estar entre 1 y {MAX_LIMIT}")
        return limit

    def collection(items: tuple[Any, ...]) -> tuple[Any, int]:
        limit = limit_value()
        serialized = [item.to_dict() for item in items[:limit]]
        return {"items": serialized, "count": len(serialized), "limit": limit}, 200

    def resource_or_404(resource: Any, resource_type: str) -> tuple[Any, int] | Any:
        if resource is None:
            payload, _ = _error_payload("not_found", f"{resource_type} no encontrado")
            return jsonify(payload), 404
        return jsonify(resource.to_dict())

    @app.get("/api/multisensor/observations")
    def list_observations():
        payload, status = collection(observation_repository.all())
        return jsonify(payload), status

    @app.get("/api/multisensor/observations/<path:observation_id>")
    def get_observation(observation_id: str):
        return resource_or_404(observation_repository.get(observation_id), "observación")

    @app.get("/api/multisensor/events")
    def list_events():
        payload, status = collection(event_repository.all())
        return jsonify(payload), status

    @app.get("/api/multisensor/events/<path:event_id>")
    def get_event(event_id: str):
        return resource_or_404(event_repository.get(event_id), "evento")

    @app.get("/api/multisensor/incidents")
    def list_incidents():
        payload, status = collection(incident_repository.all())
        return jsonify(payload), status

    @app.get("/api/multisensor/incidents/<path:incident_id>")
    def get_incident(incident_id: str):
        return resource_or_404(incident_repository.get(incident_id), "incidente")

    @app.get("/api/multisensor/sensors")
    def list_sensors():
        sensors: dict[str, dict[str, Any]] = {}
        for observation in observation_repository.all():
            sensor = sensors.setdefault(
                observation.sensor_id,
                {
                    "sensor_id": observation.sensor_id,
                    "sensor_type": observation.sensor_type,
                    "observation_count": 0,
                    "last_seen": observation.timestamp.isoformat().replace("+00:00", "Z"),
                    "_last_seen_dt": observation.timestamp,
                    "source": observation.source,
                },
            )
            sensor["observation_count"] += 1
            if observation.timestamp > sensor["_last_seen_dt"]:
                sensor["last_seen"] = observation.timestamp.isoformat().replace("+00:00", "Z")
                sensor["_last_seen_dt"] = observation.timestamp
        items = sorted(sensors.values(), key=lambda item: item["sensor_id"])
        for sensor in items:
            sensor.pop("_last_seen_dt", None)
        limit = limit_value()
        return jsonify({"items": items[:limit], "count": len(items[:limit]), "limit": limit}), 200

    @app.errorhandler(ValueError)
    def handle_bad_request(error: ValueError):
        payload, _ = _error_payload("bad_request", str(error))
        return jsonify(payload), 400

    @app.errorhandler(404)
    def handle_not_found(_error):
        payload, _ = _error_payload("not_found", "recurso no encontrado")
        return jsonify(payload), 404

    @app.errorhandler(Exception)
    def handle_internal_error(error: Exception):
        LOG.exception("Error no controlado en API multisensor: %s", error)
        payload, _ = _error_payload("internal_error", "error interno del servidor")
        return jsonify(payload), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
