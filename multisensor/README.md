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

`normalize_observation` convierte un objeto de entrada al contrato `Observation`. Los adaptadores puros están disponibles en `multisensor/adapters/`: Frigate transforma eventos `new` de `frigate/events` y PIR transforma lecturas `motion`/`active`/`state`. Ambos producen el mismo contrato canónico y pueden seleccionarse mediante `message_to_observation(sensor_type, message)`. El adaptador PIR todavía no abre un puerto ni se conecta a hardware o broker; queda listo para la siguiente integración de transporte.

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

## Correlación temporal y espacial

`TemporalSpatialCorrelator` recibe `Observation` de Frigate, PIR y WiFi-CSI y devuelve un `Correlation` basado en `Event`. La correlación requiere por defecto al menos dos tipos de sensor distintos; una cámara sola no genera una correlación. La ventana temporal predeterminada es de 5 segundos y la distancia máxima predeterminada es de 75 metros.

La puntuación es explícita y auditable:

> `evidence_weight × temporal_factor × spatial_factor × reliability_factor`

El resultado conserva en `Event.payload` los identificadores de observaciones, tipos de sensor, duración de la ventana, distancias, factores y la regla aplicada. Dos sensores temporalmente próximos elevan la evidencia; sensores incompatibles espacialmente se rechazan; una ubicación desconocida se penaliza, pero no se convierte artificialmente en incompatibilidad. El motor deduplica por conjunto de observaciones y produce un evento `multisensor_motion`, no un `Incident` ni una alerta.

```python
from multisensor.correlation import TemporalSpatialCorrelator

engine = TemporalSpatialCorrelator()
correlation = engine.ingest(observation)
if correlation:
    print(correlation.event.to_dict())
```

## WiFi-CSI

`wifi_csi_message_to_observation` acepta eventos ya procesados, no muestras CSI brutas. Requiere `sensor_id`, `timestamp`, `confidence` y `features`, conserva esas características en el payload y alimenta el mismo `Observation` que Frigate y PIR.

```python
from multisensor.adapters import message_to_observation

observation = message_to_observation("wifi_csi", {
    "sensor_id": "wifi-node-01",
    "timestamp": "2026-09-28T19:20:16Z",
    "event_type": "human_motion",
    "confidence": 0.84,
    "features": {"variance": 0.72, "fft_energy": 0.61, "threshold": 0.48},
})
```

## Fusión, evidencia e incidentes

El flujo se mantiene separado y auditable:

`Observation → Correlation → EvidenceBundle → Incident`

`FusionEngine` crea una `Evidence` por sensor y aplica la regla `sensor_confidence × temporal_factor × spatial_factor × sensor_reliability`; no suma confianzas. Dos sensores generan evidencia de un evento correlacionado. Tres sensores independientes producen un candidato a incidente. `IncidentEngine` aplica una política configurable —por defecto, tres sensores y confianza mínima de `0.5`— y crea `possible_intrusion` solo cuando se cumple el umbral.

El incidente incluye `evidence_ids`, sensores, ventana temporal, score y explicación. La creación del incidente **no envía Telegram, no modifica Cesium y no constituye por sí sola una notificación**; la política y el transporte quedan desacoplados para una fase posterior.

## Persistencia en memoria

`multisensor.persistence` ofrece interfaces `ObservationRepository`, `EvidenceRepository` e `IncidentRepository`, con implementaciones `InMemory*Repository`. Guardan entidades tipadas, permiten recuperación por ID y rechazan duplicados. El objetivo es probar el flujo completo sin PostgreSQL/PostGIS; la persistencia externa puede añadirse cuando los contratos estén estabilizados.

## Validación

Desde la raíz del repositorio se ejecuta la suite de esta fase con:

```bash
python3 -m unittest discover -s multisensor/tests -p 'test_*.py' -v
```

Los adaptadores de Frigate, PIR y WiFi-CSI, el correlador, la fusión, el motor de incidentes y los repositorios no incorporan código externo. WiFi-CSI conserva features ya procesadas, sin capturar CSI bruto. La fusión e incidentes no modifican los flujos operativos ni emiten alertas. Cuando se incorporen adaptadores o algoritmos de terceros, se documentarán su procedencia, licencia y avisos aplicables antes de reutilizar código.
