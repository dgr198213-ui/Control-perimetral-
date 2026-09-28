import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { addCameraViewshed, bearingBetween } from "./viewshed.js";

const viewer = new Cesium.Viewer("cesiumContainer", {
  baseLayerPicker: false,
  geocoder: false, // Sin búsquedas externas: la ubicación se ajusta directamente sobre el mapa.
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

// ── Estado ─────────────────────────────────────────────────────────────
const STEP = { IDLE: "idle", WAIT_POSITION: "wait_position", WAIT_HEADING: "wait_heading", EDITING: "editing" };
let step = STEP.WAIT_POSITION;
let draft = null; // { lat, lon, headingDeg, pitchDeg, fovDeg, rangeM, mountHeightM }
let previewHandle = null; // { remove } del viewshed en curso
let previewMarker = null;
const savedCameras = [];

const els = {
  fields: document.getElementById("editorFields"),
  id: document.getElementById("fId"),
  label: document.getElementById("fLabel"),
  latLon: document.getElementById("fLatLon"),
  heading: document.getElementById("fHeading"),
  headingVal: document.getElementById("fHeadingVal"),
  pitch: document.getElementById("fPitch"),
  pitchVal: document.getElementById("fPitchVal"),
  fov: document.getElementById("fFov"),
  fovVal: document.getElementById("fFovVal"),
  range: document.getElementById("fRange"),
  rangeVal: document.getElementById("fRangeVal"),
  mount: document.getElementById("fMount"),
  mountVal: document.getElementById("fMountVal"),
  btnSave: document.getElementById("btnSave"),
  btnCancel: document.getElementById("btnCancel"),
  btnExport: document.getElementById("btnExport"),
  exportBox: document.getElementById("exportBox"),
  instructions: document.getElementById("instructions"),
};

function cameraFromDraft() {
  return {
    lat: draft.lat,
    lon: draft.lon,
    headingDeg: Number(els.heading.value),
    pitchDeg: Number(els.pitch.value),
    fovDeg: Number(els.fov.value),
    rangeM: Number(els.range.value),
    mountHeightM: Number(els.mount.value),
    groundAltM: 0,
  };
}

function redrawPreview() {
  if (previewHandle) previewHandle.remove();
  previewHandle = addCameraViewshed(viewer, cameraFromDraft(), Cesium.Color.YELLOW);
}

function updateReadouts() {
  els.headingVal.textContent = els.heading.value;
  els.pitchVal.textContent = els.pitch.value;
  els.fovVal.textContent = els.fov.value;
  els.rangeVal.textContent = els.range.value;
  els.mountVal.textContent = els.mount.value;
}

[els.heading, els.pitch, els.fov, els.range, els.mount].forEach((input) => {
  input.addEventListener("input", () => {
    updateReadouts();
    redrawPreview();
  });
});

function nextAutoId() {
  return `camara_${savedCameras.length + 1}`;
}
function nextAutoLabel() {
  return `Cámara ${savedCameras.length + 1}`;
}

/** Guarda una cámara ya completa (id/label/pose) y la dibuja en verde. */
function commitCamera(camera) {
  savedCameras.push(camera);
  addCameraViewshed(viewer, camera, Cesium.Color.LIME);
  viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(camera.lon, camera.lat, camera.groundAltM ?? 0),
    point: { pixelSize: 10, color: Cesium.Color.LIME, outlineColor: Cesium.Color.BLACK, outlineWidth: 2 },
    label: {
      text: camera.label,
      font: "12px monospace",
      fillColor: Cesium.Color.LIME,
      pixelOffset: new Cesium.Cartesian2(0, -18),
    },
  });
}

function resetToWaitPosition() {
  step = STEP.WAIT_POSITION;
  draft = null;
  if (previewHandle) { previewHandle.remove(); previewHandle = null; }
  if (previewMarker) { viewer.entities.remove(previewMarker); previewMarker = null; }
  els.fields.style.display = "none";
  els.instructions.innerHTML =
    '<span class="step">1 clic</span> = colocar y afinar a mano · ' +
    '<span class="step">doble clic</span> = añadir ya con valores por defecto.';
}

els.btnCancel.addEventListener("click", resetToWaitPosition);

els.btnSave.addEventListener("click", () => {
  const camera = {
    id: els.id.value.trim() || nextAutoId(),
    label: els.label.value.trim() || nextAutoLabel(),
    ...cameraFromDraft(),
  };
  if (previewHandle) previewHandle.remove();
  if (previewMarker) { viewer.entities.remove(previewMarker); previewMarker = null; }
  commitCamera(camera);
  resetToWaitPosition();
});

// ── Interacción con el mapa ────────────────────────────────────────────
// Un clic normal en WAIT_POSITION podría ser el primero de un doble clic, así
// que se retrasa ~300ms antes de abrir el flujo guiado — si llega un segundo
// clic cercano a tiempo, se cancela y se trata como doble clic (alta rápida).
const DOUBLE_CLICK_WINDOW_MS = 300;
let pendingSingleClick = null; // { timeoutId, cartesian }

function pickGround(position) {
  return (
    viewer.scene.pickPosition(position) ??
    viewer.camera.pickEllipsoid(position, viewer.scene.globe.ellipsoid)
  );
}

function latLonOf(cartesian) {
  const carto = Cesium.Cartographic.fromCartesian(cartesian);
  return { lat: Cesium.Math.toDegrees(carto.latitude), lon: Cesium.Math.toDegrees(carto.longitude) };
}

const DEFAULT_POSE = { headingDeg: 0, pitchDeg: -15, fovDeg: 95, rangeM: 30, mountHeightM: 3 };

function quickAddAt(cartesian) {
  const { lat, lon } = latLonOf(cartesian);
  commitCamera({
    id: nextAutoId(),
    label: nextAutoLabel(),
    lat,
    lon,
    ...DEFAULT_POSE,
    groundAltM: 0,
  });
  els.instructions.innerHTML =
    `Cámara "${savedCameras[savedCameras.length - 1].id}" añadida con valores por defecto ` +
    `(heading 0°, alcance 30 m) — ajústalos luego a mano en cameras.config.js si hace falta.`;
}

function startGuidedFlow(cartesian) {
  const { lat, lon } = latLonOf(cartesian);
  draft = { lat, lon };
  previewMarker = viewer.entities.add({
    position: cartesian,
    point: { pixelSize: 10, color: Cesium.Color.YELLOW, outlineColor: Cesium.Color.BLACK, outlineWidth: 2 },
  });
  step = STEP.WAIT_HEADING;
  els.instructions.innerHTML =
    '<span class="step">2.</span> Ahora click en el mapa hacia donde apunta la cámara.';
}

const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

handler.setInputAction((click) => {
  const cartesian = pickGround(click.position);
  if (!cartesian) return;

  if (step === STEP.WAIT_POSITION) {
    // Podría ser el primer clic de un doble clic: esperamos un poco.
    pendingSingleClick = {
      cartesian,
      timeoutId: setTimeout(() => {
        pendingSingleClick = null;
        startGuidedFlow(cartesian);
      }, DOUBLE_CLICK_WINDOW_MS),
    };
    return;
  }

  if (step === STEP.WAIT_HEADING) {
    const { lat, lon } = latLonOf(cartesian);
    const headingDeg = bearingBetween(draft.lat, draft.lon, lat, lon);
    els.heading.value = Math.round(headingDeg);
    updateReadouts();
    step = STEP.EDITING;
    els.fields.style.display = "block";
    els.id.value = nextAutoId();
    els.label.value = nextAutoLabel();
    els.latLon.value = `${draft.lat.toFixed(6)}, ${draft.lon.toFixed(6)}`;
    els.instructions.innerHTML =
      '<span class="step">3.</span> Datos rellenados automáticamente — ajusta si hace falta y "Guardar cámara".';
    redrawPreview();
    return;
  }
  // step === EDITING: un click adicional en el mapa no hace nada — se usa "Cancelar" para reiniciar
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

handler.setInputAction((click) => {
  if (step !== STEP.WAIT_POSITION) return; // el doble clic solo aplica para alta rápida, no a mitad de otro flujo
  if (pendingSingleClick) {
    clearTimeout(pendingSingleClick.timeoutId);
    pendingSingleClick = null;
  }
  const cartesian = pickGround(click.position);
  if (!cartesian) return;
  quickAddAt(cartesian);
}, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

// ── Exportar a formato cameras.config.js ───────────────────────────────
els.btnExport.addEventListener("click", () => {
  if (savedCameras.length === 0) {
    alert("Todavía no has guardado ninguna cámara.");
    return;
  }
  const body = savedCameras
    .map(
      (c) => `  {
    id: "${c.id}",
    label: "${c.label}",
    lat: ${c.lat.toFixed(7)},
    lon: ${c.lon.toFixed(7)},
    headingDeg: ${c.headingDeg},
    pitchDeg: ${c.pitchDeg},
    fovDeg: ${c.fovDeg},
    rangeM: ${c.rangeM},
    mountHeightM: ${c.mountHeightM},
    groundAltM: 0,
  },`,
    )
    .join("\n");

  const text = `export const CAMERAS = [\n${body}\n];\n`;
  els.exportBox.value = text;
  els.exportBox.style.display = "block";
  els.exportBox.select();
});

resetToWaitPosition();
