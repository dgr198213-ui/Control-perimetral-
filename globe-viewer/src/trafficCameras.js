const DGT_CAMERAS_URL = import.meta.env.VITE_DGT_CAMERAS_URL || "https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v37.xml";
const CACHE_KEY = "perimetral:dgt-cameras";
const CACHE_TTL_MS = 60 * 60 * 1000;

function textOf(node) {
  return node?.textContent?.trim() || "";
}

function descendantValue(node, names) {
  const wanted = new Set(names);
  return [...node.querySelectorAll("*")].find((child) => wanted.has(child.localName?.toLowerCase()))?.textContent?.trim() || "";
}

function numberValue(value) {
  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseDgtCameras(xmlText) {
  const document = new DOMParser().parseFromString(xmlText, "application/xml");
  if (document.querySelector("parsererror")) throw new Error("XML DGT no válido");
  const nodes = [...document.querySelectorAll("*")].filter((node) => {
    const name = node.localName?.toLowerCase() || "";
    return name.includes("device") || name.includes("camera") || name.includes("record");
  });
  const byUrl = new Map();
  for (const node of nodes) {
    const latitude = numberValue(descendantValue(node, ["latitude", "lat"]));
    const longitude = numberValue(descendantValue(node, ["longitude", "lon", "long"]));
    const imageUrl = [...node.querySelectorAll("*")].map(textOf).find((value) => /^https?:\/\/.*\.(?:jpg|jpeg|png)(?:\?.*)?$/i.test(value));
    if (latitude === null || longitude === null || !imageUrl || byUrl.has(imageUrl)) continue;
    if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) continue;
    const road = descendantValue(node, ["roadnumber", "roadname", "road"]) || "Carretera DGT";
    const direction = descendantValue(node, ["direction", "directionvalue"]);
    byUrl.set(imageUrl, {
      id: `dgt:${imageUrl.split("/").pop()}`,
      source: "DGT",
      label: `${road}${direction ? ` · ${direction}` : ""}`,
      lat: latitude,
      lon: longitude,
      imageUrl,
    });
  }
  return [...byUrl.values()];
}

async function loadCameras() {
  const cached = sessionStorage.getItem(CACHE_KEY);
  if (cached) {
    const parsed = JSON.parse(cached);
    if (Date.now() - parsed.savedAt < CACHE_TTL_MS) return parsed.items;
  }
  const response = await fetch(DGT_CAMERAS_URL, { headers: { Accept: "application/xml" } });
  if (!response.ok) throw new Error(`DGT respondió ${response.status}`);
  const items = parseDgtCameras(await response.text());
  sessionStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), items }));
  return items;
}

export function startTrafficCameraLayer(viewer, { onStatus } = {}) {
  const entities = new Map();
  let stopped = false;
  async function refresh() {
    try {
      const cameras = await loadCameras();
      for (const camera of cameras) {
        const entity = viewer.entities.add({
          id: camera.id,
          position: Cesium.Cartesian3.fromDegrees(camera.lon, camera.lat, 8),
          billboard: {
            image: camera.imageUrl,
            width: 96,
            height: 64,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            show: false,
          },
          point: { pixelSize: 7, color: Cesium.Color.ORANGE, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
          label: { text: camera.label, font: "11px monospace", fillColor: Cesium.Color.ORANGE, show: false, pixelOffset: new Cesium.Cartesian2(0, -14) },
          description: `<p><strong>Fuente:</strong> DGT</p><p><strong>Imagen pública:</strong> ${camera.imageUrl}</p><p>Actualización del catálogo DGT: aproximadamente cada hora.</p>`,
        });
        entities.set(camera.id, entity);
      }
      onStatus?.(`${cameras.length} cámaras DGT cargadas`);
    } catch (error) {
      onStatus?.(`Cámaras DGT no disponibles: ${error.message}`);
    }
  }
  refresh();
  return {
    setVisible(visible) {
      for (const entity of entities.values()) {
        entity.billboard.show = visible;
        entity.label.show = visible;
      }
    },
    refresh,
    stop() { stopped = true; },
  };
}

export { DGT_CAMERAS_URL };
