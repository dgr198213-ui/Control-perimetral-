/**
 * frigateBridge.js
 *
 * Sondea periódicamente la API REST de Frigate (vía el proxy /frigate-api
 * definido en vite.config.js, para evitar CORS) y notifica los eventos
 * nuevos (persona/vehículo detectado) mediante un callback.
 *
 * No usa MQTT directamente desde el navegador (Mosquitto no expone
 * WebSockets en la configuración base del proyecto) — polling REST simple
 * es suficiente para un perímetro pequeño con pocas cámaras.
 */

const POLL_INTERVAL_MS = 3000;
const EVENTS_LIMIT = 10;

export function startFrigateBridge(onNewEvent) {
  const seenEventIds = new Set();
  let stopped = false;

  async function poll() {
    if (stopped) return;
    try {
      const res = await fetch(`/frigate-api/api/events?limit=${EVENTS_LIMIT}`);
      if (res.ok) {
        const events = await res.json();
        // Frigate devuelve los más recientes primero; los recorremos al
        // revés para notificar en orden cronológico.
        for (const ev of [...events].reverse()) {
          if (!seenEventIds.has(ev.id)) {
            seenEventIds.add(ev.id);
            onNewEvent({
              id: ev.id,
              camera: ev.camera,
              label: ev.label,
              score: ev.top_score ?? ev.score ?? null,
              startTime: ev.start_time,
            });
          }
        }
        // Evita que el Set crezca sin límite en sesiones largas
        if (seenEventIds.size > 500) {
          const arr = Array.from(seenEventIds);
          seenEventIds.clear();
          arr.slice(-200).forEach((id) => seenEventIds.add(id));
        }
      }
    } catch (err) {
      console.warn("[frigateBridge] No se pudo contactar con Frigate:", err.message);
    } finally {
      if (!stopped) setTimeout(poll, POLL_INTERVAL_MS);
    }
  }

  poll();

  return () => {
    stopped = true;
  };
}
