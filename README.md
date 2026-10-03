# Control-perimetral-

## Plataforma de analítica de seguridad para activos e infraestructura

**Control-perimetral-** es una plataforma local-first para supervisar activos, instalaciones y perímetros autorizados. Su objetivo es convertir señales de cámaras y sensores propios en **evidencia explicable, situaciones operativas, incidentes y acciones gobernadas por políticas**, reduciendo el ruido de alertas y evitando capacidades invasivas.

El producto está diseñado para organizaciones con uno o varios perímetros. El procesamiento de vídeo permanece en la infraestructura local; un backend futuro puede recibir únicamente metadatos, estados y alertas autorizadas. El sistema **no implementa biometría, reconocimiento facial ni reconocimiento automático de matrículas**.

> La vista 3D es una herramienta espacial secundaria. La interfaz principal para personas no técnicas es `dashboard/`, mientras que `globe-viewer/` sirve para contexto cartográfico y revisión avanzada de ubicaciones.

## Principios de alcance

| Principio | Aplicación técnica |
|---|---|
| Señal sobre ruido | Correlación temporal y espacial, situaciones explicables, políticas con motivo y cooldown. |
| Local-first | Frigate, MQTT, vídeo, clips y configuración operan en la red local. |
| Privacidad por diseño | No se almacenan identificadores biométricos ni identificadores WiFi de terceros; las alertas remotas son metadatos o texto. |
| Fail-closed | Sin evidencias de cumplimiento o con kill-switch activo, grabación, snapshots y notificaciones operativas permanecen bloqueadas. |
| Aislamiento | Usuarios y recursos se asocian a `tenant_id`; las consultas del API se filtran por el tenant de la sesión. |
| Explicabilidad | Cada situación e incidente conserva confianza, evidencias, explicación y referencias de origen. |

## Arquitectura funcional

```text
Sensores propios / Frigate
          │
          ▼
Observations ──► Correlation ──► Evidence ──► Events
                                             │
                                             ▼
                                 Situations ──► Incidents
                                                  │
                                                  ▼
                                      PolicyEngine ──► ActionQueue
```

| Componente | Responsabilidad | Exposición |
|---|---|---|
| Frigate | Detección y grabación local de clases genéricas | Red privada de Docker Compose |
| Mosquitto | Transporte interno de eventos | Red privada de Docker Compose |
| `multisensor` | Contratos, correlación, fusión, situaciones e incidentes | API HTTP local de lectura |
| `control-api` | Usuarios, tenants, configuración, cumplimiento, políticas y aplicación de Frigate | API autenticada mediante Caddy |
| `notifier` | Evaluación de políticas y cola durable de acciones | Servicio interno; solo emite cuando está permitido |
| `dashboard/` | Estado y configuración orientados a usuarios | Interfaz principal |
| `globe-viewer/` | Ubicación de cámaras, eventos e incidentes sobre contexto satelital | Interfaz opcional avanzada |

## Multi-tenancy

La migración SQLite `multi-tenant-isolation` añade `tenants` y asocia a cada usuario, cámara, zona, regla, secreto, perfil, estado de cumplimiento y registro de auditoría con `tenant_id`. Las rutas autenticadas resuelven el tenant desde la sesión y aplican el filtro tanto a lecturas como a escrituras. Un recurso perteneciente a otro tenant se comporta como inexistente para la sesión actual.

Las instalaciones existentes se migran al tenant `default`. La compatibilidad de la columna `compliance.id` se mantiene para operaciones locales antiguas, pero el aislamiento real utiliza `compliance.tenant_id`. La creación de organizaciones adicionales debe quedar bajo un flujo administrativo explícito antes de ofrecer autoservicio en una interfaz pública.

## Cumplimiento y kill-switch

La configuración no permite activar grabación ni snapshots hasta que existan las dos evidencias locales siguientes:

| Evidencia | Ruta |
|---|---|
| Cartelería verificada | `compliance/carteleria-verificada` |
| Encargo de tratamiento firmado | `compliance/encargo-tratamiento-firmado` |

Los archivos son marcadores locales y no contienen copias documentales. El estado efectivo se calcula siempre como:

```text
recording_allowed = signage_confirmed
                 AND mandate_confirmed
                 AND NOT kill_switch
```

Para activar o revocar el sistema se utilizan los endpoints de cumplimiento y los scripts auditados. Revocar el cumplimiento activa el kill-switch; liberarlo exige que ambas confirmaciones sigan presentes. La configuración de Frigate se escribe atómicamente y se vuelve a aplicar solo después de que el estado de cumplimiento sea válido.

## Primer arranque

```bash
cp .env.example .env
chmod 600 .env
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
# Guardar la salida en CONTROL_API_ENCRYPTION_KEY dentro de .env
docker compose config
docker compose up -d --build
```

Cuando Caddy esté saludable, abre `https://localhost:8443`, crea el usuario local inicial y verifica el estado desde el dashboard. La primera puesta en marcha permanece bloqueada hasta que se hayan verificado las evidencias de cumplimiento.

```bash
docker compose ps
docker compose logs --tail=100 control-api notifier caddy
curl -k https://localhost:8443/api/health
```

Para conservar la información, utiliza `docker compose down` sin borrar `data/` ni `storage/`. Las copias verificables se generan con `scripts/backup.sh` y la restauración exige `RESTORE_CONFIRM=YES`.

## API principal

| Ruta | Función |
|---|---|
| `POST /api/auth/setup` | Crea el usuario inicial del tenant por defecto. |
| `POST /api/auth/login` | Inicia una sesión HTTP-only asociada al usuario y su tenant. |
| `GET /api/protection-profile` | Consulta el perfil de protección del tenant. |
| `PUT /api/protection-profile` | Actualiza objetivos, modo, horarios y avisos. |
| `GET /api/protection/status` | Devuelve un estado comprensible de preparación y protección. |
| `GET /api/protection/discovery` | Descubre cámaras, zonas y reglas del tenant sin devolver secretos. |
| `GET/POST /api/cameras` | Consulta y crea cámaras locales del tenant. |
| `GET/POST /api/notification-rules` | Consulta y crea reglas explicables de notificación. |
| `GET /api/compliance` | Devuelve confirmaciones, kill-switch y `recording_allowed`. |
| `POST /api/compliance/confirm` | Confirma las evidencias mediante una operación auditada. |
| `POST /api/compliance/revoke` | Revoca cumplimiento y activa el kill-switch. |
| `POST /api/compliance/clear-kill-switch` | Libera el kill-switch solo con cumplimiento confirmado. |
| `GET /api/audit` | Consulta únicamente la auditoría del tenant actual. |
| `GET /api/metrics` | Expone métricas Prometheus del API. |

## Privacidad y límites

Todo vídeo y procesamiento de imágenes permanece en el mini-PC o red local. Las integraciones remotas, si se configuran, reciben solo texto, metadatos, estado o alertas; no se envían vídeo, snapshots ni clips. Las cámaras deben cubrir exclusivamente el perímetro autorizado y deben revisarse las reglas de conservación, el acceso físico y la documentación aplicable.

El sistema no identifica personas individualmente. Las clases genéricas de Frigate se utilizan para activar políticas operativas, no para crear perfiles personales. La vista satelital es cartografía de contexto y no representa una posición en tiempo real.

## Desarrollo y pruebas

Para probar el API de control:

```bash
PYTHONPATH=. pytest -q control-api/tests/test_api.py
```

Para probar el núcleo multisensor y los adaptadores:

```bash
PYTHONPATH=. pytest -q multisensor/tests
```

La API multisensor local puede iniciarse con:

```bash
PYTHONPATH=. python3 -m multisensor.api.app
```

El visor 3D se ejecuta por separado desde `globe-viewer/`:

```bash
cd globe-viewer
npm install
npm run dev
```

El visor consulta eventos mediante polling cada tres segundos, no se conecta directamente a MQTT y no decide por sí mismo si existe una intrusión.

## Estado del producto

La base actual incluye persistencia SQLite para el API y el dominio derivado, backups y restore, métricas, `PolicyEngine`, `ActionQueue`, `ContextEngine`, contratos `Situation`, dashboard estático, visor Cesium y controles de cumplimiento. El siguiente bloque de evolución debe completar la administración explícita de organizaciones y usuarios por tenant, incluyendo roles administrativos, aprovisionamiento de perfiles iniciales y pruebas de autorización de extremo a extremo.

## Referencias técnicas

[1]: https://docs.frigate.video/ "Documentación oficial de Frigate"
[2]: https://mosquitto.org/man/mosquitto-conf-5.html "Manual oficial de Mosquitto"
[3]: https://docs.docker.com/compose/ "Documentación oficial de Docker Compose"
[4]: https://operations.osmfoundation.org/policies/tiles/ "OpenStreetMap Tile Usage Policy"
