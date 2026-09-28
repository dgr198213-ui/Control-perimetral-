# Núcleo multisensor — Fase 0

Este directorio define el **lenguaje común** para las señales de sensores del sistema. Su incorporación es deliberadamente aislada: no cambia la configuración de Frigate, Mosquitto, Docker Compose, el notificador de Telegram, el almacenamiento ni el visor existente.

> Una observación describe lo que un sensor reportó. No constituye por sí sola una alerta ni una intrusión.

## Contratos

| Contrato | Propósito | Relación |
|---|---|---|
| `Observation` | Señal atómica de un sensor, con hora, confianza, ubicación opcional y procedencia. | Entrada canónica. |
| `Event` | Interpretación normalizada de una o más observaciones. | Conserva `observation_ids`. |
| `Evidence` | Elemento trazable que respalda un evento. | Conserva `event_id` y `sensor_id`. |
| `Incident` | Conclusión futura sustentada por evidencias identificables. | Conserva `evidence_ids` y explicación. |

Todos los tiempos deben incluir zona horaria y se normalizan a UTC. La confianza se limita al intervalo cerrado de `0` a `1`. Las coordenadas, cuando existen, se validan como latitud y longitud geográficas.

## Normalización

`normalize_observation` convierte un objeto de entrada al contrato `Observation`. El adaptador puro de Frigate está disponible en `multisensor/adapters/frigate.py`; los adaptadores de PIR y Wi-Fi CSI se añadirán en fases posteriores. El adaptador de Frigate todavía no se conecta al suscriptor MQTT del notificador, para preservar el flujo operativo existente.

```python
from multisensor.normalization import normalize_observation

observation = normalize_observation({
    "id": "obs-cam-001",
    "sensor_id": "camera-front",
    "sensor_type": "camera",
    "timestamp": "2026-09-28T19:20:14Z",
    "event_type": "person_detected",
    "confidence": 0.91,
    "location": {"lat": 43.24, "lon": -5.34},
    "payload": {"track_id": "person-42"},
    "source": "future-frigate-adapter",
})
```

## Validación

Desde la raíz del repositorio se ejecuta la suite de esta fase con:

```bash
python3 -m unittest discover -s multisensor/tests -p 'test_*.py' -v
```

El adaptador de Frigate no incorpora código externo: conserva el identificador, cámara, etiqueta, zonas, puntuación y datos relevantes del evento en la observación canónica, sin incluir credenciales. Cuando se incorporen adaptadores o algoritmos de terceros, se documentarán su procedencia, licencia y avisos aplicables antes de reutilizar código.
