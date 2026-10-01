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
| Caddy | Dashboard estático y proxy de `control-api` con TLS local | `https://CADDY_BIND_ADDRESS:8443`; HTTP en `:8080` solo redirige a HTTPS |
| Frigate | Detección local y NVR | Solo red privada de Docker Compose; el puerto interno `5000` no se publica |
| Mosquitto | Eventos MQTT internos | Solo red privada de Docker Compose; sin puerto publicado |
| `control-api` | Configuración, sesión y aplicación de la configuración de Frigate | Solo a través de Caddy bajo `/api/*` |
| Notificador | Filtrado por clase/zona y alerta textual | Salida HTTPS a Telegram únicamente cuando está desbloqueado |
| `storage/` y `data/` | Datos, clips y configuración local generada | Volúmenes locales, nunca sincronizados a la nube por este proyecto |

Frigate utiliza clases genéricas (`person`, `car`, `motorcycle` y `bicycle`). La detección de drones **no está garantizada** y no se presenta como una capacidad disponible del modelo base.

## Preparación

Instala Docker Engine con Compose en el mini-PC local y coloca las cámaras en una red controlada. Copia la plantilla de variables:

```bash
cp .env.example .env
chmod 600 .env
```

Rellena `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` solo en `.env`. El proyecto no envía vídeo, imágenes ni snapshots a Telegram; las alertas son texto con clase, cámara, zona y hora.

La plantilla `frigate/config.template.yml` se copia una única vez a `data/frigate-config/config.yml` al iniciar el stack. No edites la plantilla para dar de alta cámaras: la configuración activa se genera desde `control-api`, que conserva los secretos fuera del YAML y aplica las cámaras y zonas autorizadas. No reutilices este proyecto para otra finca sin una revisión separada de permisos, zonas y documentación.

## Arranque seguro de pruebas

La primera ejecución no graba:

```bash
docker compose config
docker compose up -d
```

El dashboard y la API estarán en `https://localhost:8443`; el puerto `8080` solo redirige a HTTPS. `CADDY_HOSTNAME` debe ser exactamente el nombre o la IP que se usará en el navegador, porque identifica el certificado local. Para acceso LAN, establece `CADDY_HOSTNAME` y `CADDY_BIND_ADDRESS` con la IP LAN del mini-PC, restringe el puerto con el firewall y no hagas *port-forwarding* a Internet.

Caddy emite un certificado mediante su CA local. Tras el primer arranque, instala `storage/caddy-data/caddy/pki/authorities/local/root.crt` en el almacén de autoridades de confianza del navegador y de cada móvil autorizado. Reinicia el navegador o la aplicación después de importarlo y accede siempre por HTTPS con el valor de `CADDY_HOSTNAME`. Esta CA sirve únicamente para este despliegue local: no la copies a dispositivos no controlados ni la publiques. Para una comprobación de línea de comandos, puedes usar el mismo certificado como CA:

```bash
curl --cacert storage/caddy-data/caddy/pki/authorities/local/root.crt https://localhost:8443/api/health
```

Puedes comprobar el bloqueo con:

```bash
grep -A2 '^record:' data/frigate-config/config.yml
grep -A2 '^snapshots:' data/frigate-config/config.yml
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

## Aplicación de la configuración de Frigate

`control-api` escribe de forma atómica el YAML renderizado en `data/frigate-config/config.yml`. Frigate monta ese directorio en `/config-generated` en modo de solo lectura y recibe `CONFIG_FILE=/config-generated/config.yml`; Frigate 0.16.2 resuelve explícitamente esa variable antes de usar `/config/config.yml` como valor predeterminado. Después, `control-api` solicita `POST /api/restart` a `http://frigate:5000` dentro de la red privada de Compose. El puerto interno no se publica y este flujo no monta ni utiliza `docker.sock`. [5]

La configuración generada incluye `version: 0.16-0`, por lo que Frigate no necesita migrarla. En el arranque puede aparecer el mensaje `Config file is read-only, unable to migrate config file.` porque el volumen es deliberadamente de solo lectura para Frigate; la validación funcional se considera correcta cuando el contenedor permanece saludable y los logs muestran `Starting Frigate (0.16.2-...)`.

Si Frigate no confirma el reinicio, `POST /api/frigate/render` responde con `502` después de haber preservado el archivo generado. Revisa `docker compose logs frigate`, corrige el problema y vuelve a aplicar la configuración. Los scripts de activación y desactivación operan sobre el mismo archivo activo y requieren la recreación explícita indicada en sus mensajes.

## Privacidad y límites

El procesamiento de vídeo se realiza dentro del mini-PC y el stack no publica el broker MQTT. Telegram recibe solo texto cuando se cumplen las condiciones de activación. No hay reconocimiento facial ni identificación biométrica. El modelo estándar no ofrece una detección fiable de drones; cualquier investigación futura deberá evaluarse por separado, incluyendo falsos positivos, datos de entrenamiento y exposición de imágenes.

Las cámaras deben apuntar únicamente al perímetro autorizado. No uses el sistema para vigilar espacios públicos, viviendas colindantes o zonas ajenas a la finca. Revisa periódicamente los logs, el almacenamiento y las reglas de retención, y elimina los datos cuando venza el plazo definido por el responsable.

## Protección orientada al usuario

La API de control incorpora un único **perfil de protección** persistente para expresar el tipo de sitio, el nivel de protección, los objetivos de detección, la protección nocturna, los avisos y las horas tranquilas. Los valores por defecto priorizan personas y vehículos, mantienen el modo equilibrado y no activan la detección de animales. Las rutas requieren una sesión autenticada y las modificaciones quedan registradas en el *audit log*.

| Ruta | Función |
|---|---|
| `GET /api/protection-profile` | Consulta el perfil de protección activo. |
| `PUT /api/protection-profile` | Actualiza el perfil tras validar valores, horarios y tipos. |
| `GET /api/protection/status` | Devuelve un estado comprensible (`setup_required`, `attention` o `protected`) basado en cámaras, zonas, reglas y cumplimiento existentes. |
| `GET /api/protection/discovery` | Descubre recursos persistidos —cámaras, zonas y reglas— y comprueba de forma controlada la disponibilidad de Frigate y MQTT. |
| `GET /api/protection/recommendations` | Devuelve recomendaciones deterministas respaldadas por el estado real de la configuración. |

El núcleo multisensor añade el contrato inmutable `Situation` y un `SituationEngine` puro que clasifica un `Event` como `activity_detected` o `suspicious_activity` usando la confianza que ya calcula la correlación. El motor no persiste, no envía notificaciones, no crea acciones y no convierte automáticamente una situación en incidente.

El autodiscovery devuelve una respuesta tipada y limitada a un máximo de 1.000 elementos por recurso. Cada colección informa de `count`, `returned_count` y `truncated`, diferenciando el total persistido de los elementos serializados. La API nunca incluye hosts RTSP, rutas, nombres de usuario, contraseñas ni secretos cifrados. Para Frigate se consulta el endpoint interno de versión con un tiempo de espera de dos segundos; para MQTT se comprueba únicamente la apertura TCP, sin publicar ni suscribirse a temas. Los estados de integración son `reachable`, `unavailable` o `not_verified` cuando la comprobación se desactiva durante pruebas.

> El repositorio no contiene todavía una implementación funcional del dashboard: `dashboard/` solo conserva un marcador. Por ello, esta entrega expone la configuración y el estado mediante la API, sin presentar una interfaz nueva ni alterar el visor 3D opcional.

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
[5]: https://github.com/blakeblackshear/frigate/blob/v0.16.2/frigate/api/app.py#L567-L584 "Frigate 0.16.2 — endpoint POST /api/restart"
