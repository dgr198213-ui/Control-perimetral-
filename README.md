# Seguridad Perimetral — detección local

Sistema de videovigilancia inteligente para **una única finca de un tercero con permiso explícito del propietario**. Procesa los streams RTSP en la máquina local, detecta clases genéricas y envía alertas de texto a Telegram. No incorpora reconocimiento facial, biometría ni identificación de personas.

## Condición de activación no negociable

La configuración versionada mantiene **desactivadas la grabación y las snapshots**. No se debe habilitar la grabación de personas hasta que se hayan cumplido simultáneamente estas condiciones:

| Condición | Evidencia local requerida |
|---|---|
| Cartelería de videovigilancia visible en la finca | `compliance/carteleria-verificada` |
| Documento de encargo de tratamiento firmado con el propietario | `compliance/encargo-tratamiento-firmado` |

Los archivos son marcadores, no copias de documentos. El contenido de las evidencias no se lee ni se envía a terceros. El directorio está excluido de Git.

## Arquitectura

| Componente | Función | Exposición |
|---|---|---|
| Frigate | Detección local, dashboard y NVR | Dashboard en `DASHBOARD_BIND_ADDRESS:5000`; por defecto solo localhost |
| Mosquitto | Eventos MQTT internos | Solo red privada de Docker Compose; sin puerto publicado |
| Notificador | Filtrado por clase/zona y alerta textual | Salida HTTPS a Telegram únicamente cuando está desbloqueado |
| `storage/` | Datos y clips locales | Volumen local, nunca sincronizado a la nube por este proyecto |

Frigate utiliza clases genéricas (`person`, `car`, `motorcycle` y `bicycle`). La detección de drones **no está garantizada** y no se presenta como una capacidad disponible del modelo base.

## Preparación

Instala Docker Engine con Compose en el mini-PC local y coloca las cámaras en una red controlada. Copia la plantilla de variables:

```bash
cp .env.example .env
chmod 600 .env
```

Rellena `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` solo en `.env`. El proyecto no envía vídeo, imágenes ni snapshots a Telegram; las alertas son texto con clase, cámara, zona y hora.

Edita `frigate/config.yml` y sustituye las URLs RTSP de ejemplo por las cámaras autorizadas. Ajusta la resolución, FPS y el polígono de `zona_perimetro` desde el dashboard. No reutilices este proyecto para otra finca sin una revisión separada de permisos, zonas y documentación.

## Arranque seguro de pruebas

La primera ejecución no graba:

```bash
docker compose config
docker compose up -d
```

El dashboard estará en `http://127.0.0.1:5000` o en la IP LAN configurada en `DASHBOARD_BIND_ADDRESS`. Si se habilita el acceso desde la LAN, restringe el puerto con el firewall del mini-PC y no hagas port-forwarding a Internet.

Puedes comprobar el bloqueo con:

```bash
grep -A2 '^record:' frigate/config.yml
grep -A2 '^snapshots:' frigate/config.yml
docker compose logs notifier
```

Mientras no existan los dos marcadores de `compliance/`, el notificador descarta eventos relevantes y no envía alertas a Telegram.

## Activación documentada

Solo una persona autorizada debe crear los dos marcadores después de verificar personalmente las condiciones:

```bash
touch compliance/carteleria-verificada compliance/encargo-tratamiento-firmado
./scripts/enable-recording.sh
docker compose up -d --force-recreate frigate notifier
```

El script aborta si falta cualquiera de las dos evidencias y crea una copia de seguridad de la configuración anterior. Para desactivar inmediatamente:

```bash
./scripts/disable-recording.sh
docker compose up -d --force-recreate frigate notifier
```

La activación de grabación no sustituye la revisión de la base jurídica, los plazos de conservación, los derechos de las personas afectadas ni las obligaciones documentales aplicables. Este repositorio implementa controles técnicos y no constituye asesoramiento jurídico.

## Privacidad y límites

El procesamiento de vídeo se realiza dentro del mini-PC y el stack no publica el broker MQTT. Telegram recibe solo texto cuando se cumplen las condiciones de activación. No hay reconocimiento facial ni identificación biométrica. El modelo estándar no ofrece una detección fiable de drones; cualquier investigación futura deberá evaluarse por separado, incluyendo falsos positivos, datos de entrenamiento y exposición de imágenes.

Las cámaras deben apuntar únicamente al perímetro autorizado. No uses el sistema para vigilar espacios públicos, viviendas colindantes o zonas ajenas a la finca. Revisa periódicamente los logs, el almacenamiento y las reglas de retención, y elimina los datos cuando venza el plazo definido por el responsable.

## API HTTP multisensor

El núcleo multisensor expone una API HTTP de solo lectura mediante `multisensor.api`. La auditoría del repositorio no encontró un framework HTTP existente; por eso esta primera versión usa Flask únicamente como adaptador de transporte, sin duplicar reglas de correlación, fusión o incidentes.

Las rutas disponibles son:

| Ruta | Contenido |
|---|---|
| `GET /api/multisensor/observations` | Colección de observaciones canónicas. |
| `GET /api/multisensor/observations/{id}` | Observación concreta. |
| `GET /api/multisensor/events` | Eventos correlacionados. |
| `GET /api/multisensor/events/{id}` | Evento concreto con `observation_ids`. |
| `GET /api/multisensor/incidents` | Incidentes producidos por `IncidentEngine`. |
| `GET /api/multisensor/incidents/{id}` | Incidente con `evidence_ids`, score y explicación. |
| `GET /api/multisensor/sensors` | Sensores derivados de las observaciones almacenadas. |

Las respuestas mantienen timestamps UTC, IDs, scores, referencias y explicaciones de los contratos de dominio. Las colecciones aceptan `?limit=1..1000`. Los errores se serializan como `bad_request` (400), `not_found` (404) o `internal_error` (500). La aplicación recibe repositorios por inyección; por defecto usa los repositorios en memoria. Todavía no se añaden PostgreSQL/PostGIS, Cesium, Telegram ni webhooks.

Para ejecutar localmente, instala `multisensor/api/requirements.txt` y arranca:

```bash
python3 -m pip install -r multisensor/api/requirements.txt
python3 -m multisensor.api.app
```

## Visor 3D opcional

`globe-viewer/` es una utilidad separada para visualizar posiciones configuradas de cámaras. No participa en la detección, no sustituye al dashboard de Frigate y debe completarse con coordenadas autorizadas antes de usarse.

## Referencias técnicas

[1]: https://docs.frigate.video/ "Documentación oficial de Frigate"
[2]: https://mosquitto.org/man/mosquitto-conf-5.html "Manual oficial de configuración de Mosquitto"
[3]: https://core.telegram.org/bots/api#sendmessage "Telegram Bot API — sendMessage"
[4]: https://docs.docker.com/compose/ "Documentación oficial de Docker Compose"
