/**
 * Cliente de solo lectura para la API multisensor.
 *
 * El navegador no decide si existe una intrusión: solo representa los
 * contratos producidos por el backend. Polling HTTP evita exponer MQTT y
 * mantiene compatible el despliegue local actual.
 */

const DEFAULT_INTERVAL_MS = 3000;
const DEFAULT_LIMIT = 100;

export function startMultisensorBridge({
  onObservation = () => {},
  onIncident = () => {},
  onError = () => {},
  intervalMs = DEFAULT_INTERVAL_MS,
  limit = DEFAULT_LIMIT,
} = {}) {
  let stopped = false;
  let timer = null;
  const seenObservations = new Set();
  const seenIncidents = new Set();

  async function fetchCollection(path) {
    const response = await fetch(`${path}?limit=${encodeURIComponent(limit)}`);
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        detail = payload?.error?.message || detail;
      } catch {
        // Mantiene el error HTTP original cuando el servidor no devuelve JSON.
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function emitNew(items, seen, callback) {
    for (const item of [...items].reverse()) {
      if (!item?.id || seen.has(item.id)) continue;
      seen.add(item.id);
      callback(item);
    }
    if (seen.size > 1000) {
      const retained = [...seen].slice(-500);
      seen.clear();
      retained.forEach((id) => seen.add(id));
    }
  }

  async function poll() {
    if (stopped) return;
    try {
      const [observations, incidents] = await Promise.all([
        fetchCollection("/multisensor-api/api/multisensor/observations"),
        fetchCollection("/multisensor-api/api/multisensor/incidents"),
      ]);
      emitNew(observations?.items || [], seenObservations, onObservation);
      emitNew(incidents?.items || [], seenIncidents, onIncident);
    } catch (error) {
      onError(error);
    } finally {
      if (!stopped) timer = setTimeout(poll, intervalMs);
    }
  }

  poll();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}
