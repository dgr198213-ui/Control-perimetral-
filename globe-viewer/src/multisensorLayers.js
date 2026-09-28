import * as Cesium from "cesium";

const OBSERVATION_COLORS = {
  camera: Cesium.Color.ORANGE,
  pir: Cesium.Color.YELLOW,
  wifi_csi: Cesium.Color.MAGENTA,
};

function locationOf(item) {
  const location = item?.location;
  if (!location || !Number.isFinite(location.latitude) || !Number.isFinite(location.longitude)) {
    return null;
  }
  return location;
}

function timeLabel(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "hora desconocida" : date.toLocaleString();
}

export function createMultisensorLayers(viewer) {
  const observationEntities = new Map();
  const incidentEntities = new Map();

  function upsertObservation(observation) {
    const location = locationOf(observation);
    if (!location) return false;
    const color = OBSERVATION_COLORS[observation.sensor_type] || Cesium.Color.WHITE;
    let entity = observationEntities.get(observation.id);
    if (!entity) {
      entity = viewer.entities.add({ id: `observation:${observation.id}` });
      observationEntities.set(observation.id, entity);
    }
    entity.position = Cesium.Cartesian3.fromDegrees(location.longitude, location.latitude, 2);
    entity.point = {
      pixelSize: 9,
      color: color.withAlpha(0.9),
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 1,
    };
    entity.label = {
      text: `${observation.sensor_type} · ${observation.event_type}`,
      font: "12px monospace",
      fillColor: color,
      showBackground: true,
      backgroundColor: Cesium.Color.BLACK.withAlpha(0.65),
      pixelOffset: new Cesium.Cartesian2(0, -18),
      show: false,
    };
    entity.description = [
      `<strong>Observación</strong>`,
      `ID: ${observation.id}`,
      `Sensor: ${observation.sensor_id}`,
      `Tipo: ${observation.event_type}`,
      `Confianza: ${Math.round((observation.confidence || 0) * 100)}%`,
      `Hora UTC: ${timeLabel(observation.timestamp)}`,
    ].join("<br>");
    return true;
  }

  function upsertIncident(incident) {
    const location = locationOf(incident);
    if (!location) return false;
    let entity = incidentEntities.get(incident.id);
    if (!entity) {
      entity = viewer.entities.add({ id: `incident:${incident.id}` });
      incidentEntities.set(incident.id, entity);
    }
    entity.position = Cesium.Cartesian3.fromDegrees(location.longitude, location.latitude, 4);
    entity.point = {
      pixelSize: 16,
      color: Cesium.Color.RED,
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 2,
    };
    entity.label = {
      text: `INCIDENTE · ${incident.incident_type}`,
      font: "bold 13px monospace",
      fillColor: Cesium.Color.RED,
      showBackground: true,
      backgroundColor: Cesium.Color.BLACK.withAlpha(0.8),
      pixelOffset: new Cesium.Cartesian2(0, -24),
    };
    entity.description = [
      `<strong>Incidente</strong>`,
      `ID: ${incident.id}`,
      `Tipo: ${incident.incident_type}`,
      `Estado: ${incident.status}`,
      `Confianza: ${Math.round((incident.confidence || 0) * 100)}%`,
      `Evidencias: ${(incident.evidence_ids || []).join(", ")}`,
      `Explicación: ${incident.explanation || "sin explicación"}`,
      `Inicio UTC: ${timeLabel(incident.started_at)}`,
    ].join("<br>");
    return true;
  }

  return {
    upsertObservation,
    upsertIncident,
    clear() {
      for (const entity of [...observationEntities.values(), ...incidentEntities.values()]) {
        viewer.entities.remove(entity);
      }
      observationEntities.clear();
      incidentEntities.clear();
    },
  };
}
