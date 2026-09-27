/**
 * viewshed.js
 *
 * Geometría del cono de cobertura ("viewshed") de una cámara: a partir de su
 * posición y orientación (lat/lon/heading/pitch/fov/alcance), calcula el
 * frustum piramidal que representa lo que la cámara "ve".
 *
 * ORIGEN: la matemática de proyección (projectPoint, planeDimensions) y la
 * construcción del volumen (createFrustumVolumePrimitive) están adaptadas de
 * bilawalsidhu/gods-eye-view (MIT License, Copyright (c) 2026 Bilawal Sidhu):
 *   - src/data/cctvFootprint.js  (projectPoint, planeDimensions)
 *   - src/data/cctvViewshed.js   (createFrustumVolumePrimitive)
 *   - src/layers/cctv/geometry.js (estructura de computeFrustumGeometry)
 * https://github.com/bilawalsidhu/gods-eye-view
 *
 * Simplificado para uso propio: sin muestreo de terreno/DEM, sin Google 3D
 * Tiles, sin calibración interactiva — pensado para un único perímetro fijo
 * con la pose de cámara introducida a mano en cameras.config.js.
 */
import * as Cesium from "cesium";

const EARTH_RADIUS_M = 6371000;
const PLANE_VERT_ASPECT = 16 / 9;

const toRad = (deg) => (deg * Math.PI) / 180;
const toDeg = (rad) => (rad * 180) / Math.PI;
const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

/** Desplaza un lat/lon una distancia (m) siguiendo un rumbo (grados). */
export function projectPoint(lat, lon, headingDeg, distM) {
  const b = toRad(headingDeg);
  const la = toRad(lat);
  const lo = toRad(lon);
  const ad = distM / EARTH_RADIUS_M;
  const la2 = Math.asin(
    Math.sin(la) * Math.cos(ad) + Math.cos(la) * Math.sin(ad) * Math.cos(b),
  );
  const lo2 =
    lo +
    Math.atan2(
      Math.sin(b) * Math.sin(ad) * Math.cos(la),
      Math.cos(ad) - Math.sin(la) * Math.sin(la2),
    );
  return { lat: toDeg(la2), lon: toDeg(lo2) };
}

/**
 * Rumbo inicial (grados de brújula, 0-360) desde un punto (lat1,lon1) hacia
 * otro (lat2,lon2). Es la operación inversa de projectPoint: se usa en la
 * calibración para deducir el heading de la cámara a partir de dos clics en
 * el mapa (dónde está la cámara, hacia dónde mira).
 */
export function bearingBetween(lat1, lon1, lat2, lon2) {
  const la1 = toRad(lat1);
  const la2 = toRad(lat2);
  const dLon = toRad(lon2 - lon1);
  const y = Math.sin(dLon) * Math.cos(la2);
  const x =
    Math.cos(la1) * Math.sin(la2) - Math.sin(la1) * Math.cos(la2) * Math.cos(dLon);
  const bearing = toDeg(Math.atan2(y, x));
  return (bearing + 360) % 360;
}

/** Dimensiones del "plano lejano" del frustum para una pose dada. */
export function planeDimensions({ pitchDeg, fovDeg, rangeM }) {
  const R = Math.max(1, Number(rangeM) || 1);
  const pitch = toRad(clamp(Number(pitchDeg) || 0, -89, 89));
  const hFov = toRad(clamp(Number(fovDeg) || 74, 8, 160));
  const halfW = R * Math.tan(hFov / 2);
  const vFovRad = 2 * Math.atan(Math.tan(hFov / 2) / PLANE_VERT_ASPECT);
  const halfH = R * Math.tan(vFovRad / 2);
  return {
    halfW,
    halfH,
    horiz: R * Math.cos(pitch),
    vert: R * Math.sin(pitch),
    upVert: Math.cos(pitch) * halfH,
    upHoriz: -Math.sin(pitch) * halfH,
  };
}

/**
 * Calcula los 5 puntos (mount + 4 esquinas del plano lejano) del frustum,
 * en lat/lon/alt, a partir de la pose de la cámara.
 * @param {{lat:number, lon:number, headingDeg:number, pitchDeg:number,
 *   fovDeg:number, rangeM:number, mountHeightM:number}} camera
 * @param {number} groundAltM Altitud del suelo en la base de la cámara.
 */
export function computeFrustumGeometry(camera, groundAltM = 0) {
  const heading = Number(camera.headingDeg) || 0;
  const mountAlt = groundAltM + (Number(camera.mountHeightM) || 3);
  const dims = planeDimensions(camera);

  const capLL = projectPoint(camera.lat, camera.lon, heading, dims.horiz);
  const capAlt = mountAlt + dims.vert;
  const capL = projectPoint(capLL.lat, capLL.lon, heading - 90, dims.halfW);
  const capR = projectPoint(capLL.lat, capLL.lon, heading + 90, dims.halfW);

  const corner = (base, sign) => {
    const ll = projectPoint(base.lat, base.lon, heading, sign * dims.upHoriz);
    return { lat: ll.lat, lon: ll.lon, alt: capAlt + sign * dims.upVert };
  };

  return {
    mount: { lat: camera.lat, lon: camera.lon, alt: mountAlt },
    corners: {
      tl: corner(capL, 1),
      tr: corner(capR, 1),
      br: corner(capR, -1),
      bl: corner(capL, -1),
    },
  };
}

/** Convierte el resultado de computeFrustumGeometry a Cartesian3 (ECEF). */
export function frustumCartesians(geometry) {
  const at = (p) => Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.alt);
  return {
    mount: at(geometry.mount),
    tl: at(geometry.corners.tl),
    tr: at(geometry.corners.tr),
    br: at(geometry.corners.br),
    bl: at(geometry.corners.bl),
  };
}

/** Construye el volumen translúcido (pirámide) del frustum para una cámara. */
export function createFrustumVolumePrimitive(positions, color) {
  const pts = [positions.mount, positions.tl, positions.tr, positions.br, positions.bl];
  const flat = new Float64Array(15);
  pts.forEach((p, i) => {
    flat[i * 3] = p.x;
    flat[i * 3 + 1] = p.y;
    flat[i * 3 + 2] = p.z;
  });
  const indices = new Uint16Array([0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 1, 1, 2, 3, 1, 3, 4]);
  const geometry = new Cesium.Geometry({
    attributes: {
      position: new Cesium.GeometryAttribute({
        componentDatatype: Cesium.ComponentDatatype.DOUBLE,
        componentsPerAttribute: 3,
        values: flat,
      }),
    },
    indices,
    primitiveType: Cesium.PrimitiveType.TRIANGLES,
    boundingSphere: Cesium.BoundingSphere.fromVertices(Array.from(flat)),
  });
  return new Cesium.Primitive({
    geometryInstances: new Cesium.GeometryInstance({
      geometry,
      attributes: {
        color: Cesium.ColorGeometryInstanceAttribute.fromColor(color),
      },
    }),
    appearance: new Cesium.PerInstanceColorAppearance({
      flat: true,
      translucent: true,
      renderState: { cull: { enabled: false } },
    }),
    asynchronous: false,
    allowPicking: false,
  });
}

/** Dibuja el frustum completo (volumen + contorno) de una cámara en el visor.
 * Devuelve las referencias (primitive + entities) para poder borrarlo, útil
 * en la calibración interactiva donde el viewshed se redibuja al mover un
 * slider. */
export function addCameraViewshed(viewer, camera, color = Cesium.Color.CYAN) {
  const geometry = computeFrustumGeometry(camera, camera.groundAltM ?? 0);
  const positions = frustumCartesians(geometry);

  const fillColor = color.withAlpha(0.15);
  const lineColor = color.withAlpha(0.8);

  const volume = createFrustumVolumePrimitive(positions, fillColor);
  viewer.scene.primitives.add(volume);

  // Contorno: 4 aristas desde la cámara + rectángulo del plano lejano
  const edges = [
    [positions.mount, positions.tl],
    [positions.mount, positions.tr],
    [positions.mount, positions.br],
    [positions.mount, positions.bl],
    [positions.tl, positions.tr],
    [positions.tr, positions.br],
    [positions.br, positions.bl],
    [positions.bl, positions.tl],
  ];
  const lineEntities = edges.map(([a, b]) =>
    viewer.entities.add({
      polyline: {
        positions: [a, b],
        width: 1.5,
        material: lineColor,
      },
    }),
  );

  function remove() {
    viewer.scene.primitives.remove(volume);
    lineEntities.forEach((e) => viewer.entities.remove(e));
  }

  return { geometry, positions, remove };
}
