/**
 * cameras.config.js
 *
 * Define aquí la pose real de cada cámara del perímetro. Estos valores no se
 * pueden inventar — hay que medirlos/estimarlos en el sitio real:
 *
 *  - lat, lon: posición GPS de la cámara (Google Maps: mantener pulsado el
 *    punto exacto te da las coordenadas).
 *  - headingDeg: hacia dónde apunta la cámara, en grados de brújula
 *    (0 = Norte, 90 = Este, 180 = Sur, 270 = Oeste).
 *  - pitchDeg: inclinación vertical (negativo = mirando hacia abajo).
 *  - fovDeg: campo de visión horizontal de la cámara (dato del fabricante,
 *    suele estar en la ficha técnica — típico 90-110° en cámaras de exterior).
 *  - rangeM: alcance útil de detección fiable en metros (no el alcance óptico
 *    teórico — el alcance real al que el modelo detecta personas con
 *    confianza; empieza siendo conservador, ej. 25-40 m, y ajusta con datos
 *    reales de Frigate).
 *  - mountHeightM: altura de montaje de la cámara sobre el suelo, en metros.
 *
 * El nombre de cada entrada (camara_1, camara_2...) debe coincidir con el
 * nombre de la cámara en frigate/config.yml, porque así se cruzan los
 * eventos de Frigate con la pose para dibujar el viewshed correcto.
 */
export const CAMERAS = [
  {
    id: "camara_1",
    label: "Cámara 1",
    lat: 0.0, // TODO: coordenada real
    lon: 0.0, // TODO: coordenada real
    headingDeg: 0, // TODO
    pitchDeg: -15,
    fovDeg: 95,
    rangeM: 30,
    mountHeightM: 3,
    groundAltM: 0,
  },
  {
    id: "camara_2",
    label: "Cámara 2",
    lat: 0.0, // TODO: coordenada real
    lon: 0.0, // TODO: coordenada real
    headingDeg: 0, // TODO
    pitchDeg: -15,
    fovDeg: 95,
    rangeM: 30,
    mountHeightM: 3,
    groundAltM: 0,
  },
];
