import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { addCameraViewshed } from "./viewshed.js";
import { startFrigateBridge } from "./frigateBridge.js";
import { startMultisensorBridge } from "./multisensorBridge.js";
import { createMultisensorLayers } from "./multisensorLayers.js";
import { CAMERAS as EXAMPLE_CAMERAS } from "./cameras.config.example.js";

// Configuración real opcional, ignorada por Git. En Vercel o una instalación
// limpia no existe y se conserva el fallback ficticio para que la build funcione.
const localConfig = import.meta.glob("./cameras.config.js", { eager: true });
const CAMERAS = Object.values(localConfig)[0]?.CAMERAS ?? EXAMPLE_CAMERAS;

// ── Globo base ──────────────────────────────────────────────────────────
// Imagería Esri satélite: sin clave, sin coste. Coherente con "presupuesto
// mínimo/gratuito" — si más adelante quieres 3D fotorrealista, sigue las
// instrucciones de God's Eye View para añadir un token de Cesium ion.
const viewer = new Cesium.Viewer("cesiumContainer", {
  baseLayerPicker: false,
  geocoder: false,
  homeButton: true,
  sceneModePicker: false,
  navigationHelpButton: false,
  animation: false,
  timeline: false,
  fullscreenButton: false,
  baseLayer: new Cesium.ImageryLayer(
    new Cesium.UrlTemplateImageryProvider({
      url:
        "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      credit: "Esri World Imagery",
    }),
  ),
});

// ── Cámaras del perímetro: marcador + cono de cobertura (viewshed) ───────
const cameraMarkers = {};
const pulseTimeouts = {};

CAMERAS.forEach((camera, i) => {
  const position = Cesium.Cartesian3.fromDegrees(
    camera.lon,
    camera.lat,
    camera.groundAltM + camera.mountHeightM,
  );

  cameraMarkers[camera.id] = viewer.entities.add({
    position,
    point: {
      pixelSize: 10,
      color: Cesium.Color.CYAN,
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 2,
    },
    label: {
      text: camera.label,
      font: "14px monospace",
      fillColor: Cesium.Color.CYAN,
      pixelOffset: new Cesium.Cartesian2(0, -20),
    },
  });

  addCameraViewshed(viewer, camera, Cesium.Color.CYAN);
});

// Encuadra la vista sobre las cámaras configuradas al arrancar
if (CAMERAS.some((c) => c.lat !== 0 || c.lon !== 0)) {
  viewer.zoomTo(viewer.entities);
} else {
  console.warn(
    "[perímetro] Rellena las coordenadas reales en src/cameras.config.js — " +
      "el globo está centrado en 0,0 (placeholder).",
  );
}

// ── Eventos de detección en tiempo real (Frigate) ─────────────────────────
const eventFeedEl = document.getElementById("eventFeed");
const multisensorStatusEl = document.getElementById("multisensorStatus");
const eventLines = [];
const multisensorLayers = createMultisensorLayers(viewer);

function pulseCamera(cameraId, label) {
  const entity = cameraMarkers[cameraId];
  if (!entity) return;

  // Pulso visual: agranda y vuelve a encoger el punto de la cámara
  const original = 10;
  if (pulseTimeouts[cameraId]) clearTimeout(pulseTimeouts[cameraId]);
  entity.point.pixelSize = 22;
  entity.point.color = Cesium.Color.RED;
  pulseTimeouts[cameraId] = setTimeout(() => {
    entity.point.pixelSize = original;
    entity.point.color = Cesium.Color.CYAN;
    delete pulseTimeouts[cameraId];
  }, 1500);
}

function logEvent({ camera, label, score, startTime }) {
  const hora = new Date(startTime * 1000).toLocaleTimeString();
  const pct = score ? ` (${Math.round(score * 100)}%)` : "";
  eventLines.unshift(`[${hora}] ${camera}: ${label}${pct}`);
  eventLines.splice(10); // conserva solo los últimos 10
  eventFeedEl.textContent = eventLines.join("\n");
}

startFrigateBridge(({ camera, label, score, startTime }) => {
  pulseCamera(camera, label);
  logEvent({ camera, label, score, startTime });
});

function logMultisensor(kind, item) {
  const prefix = kind === "incident" ? "INCIDENTE" : item.sensor_type;
  const id = item.id || "sin-id";
  eventLines.unshift(`[${new Date().toLocaleTimeString()}] ${prefix}: ${id}`);
  eventLines.splice(10);
  eventFeedEl.textContent = eventLines.join("\n");
}

startMultisensorBridge({
  onObservation: (observation) => {
    multisensorLayers.upsertObservation(observation);
    logMultisensor("observation", observation);
    if (multisensorStatusEl) multisensorStatusEl.textContent = "Multisensor: conectado";
  },
  onIncident: (incident) => {
    multisensorLayers.upsertIncident(incident);
    logMultisensor("incident", incident);
    if (multisensorStatusEl) multisensorStatusEl.textContent = "Multisensor: incidente recibido";
  },
  onError: (error) => {
    if (multisensorStatusEl) multisensorStatusEl.textContent = `Multisensor: sin conexión (${error.message})`;
    console.warn("[multisensorBridge] API no disponible:", error.message);
  },
});
