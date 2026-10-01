# Evidencias de cumplimiento

Este directorio debe contener, únicamente en la máquina local y fuera de Git, dos archivos vacíos o marcadores internos que acrediten que el responsable ha verificado las condiciones de activación:

| Archivo | Significado |
|---|---|
| `carteleria-verificada` | La cartelería de videovigilancia está instalada y visible en la finca. |
| `encargo-tratamiento-firmado` | Existe un documento de encargo de tratamiento firmado con el propietario. |

El notificador solo envía alertas si ambos archivos existen. El contenido de las evidencias no se lee ni se transmite. No guardes aquí copias del contrato, fotografías de carteles ni datos personales.

Crea los marcadores solo después de que el responsable autorizado haya hecho la comprobación correspondiente:

```bash
touch compliance/carteleria-verificada compliance/encargo-tratamiento-firmado
./scripts/enable-recording.sh
docker compose up -d --force-recreate frigate notifier
```

Para bloquear de nuevo el sistema:

```bash
./scripts/disable-recording.sh
docker compose up -d --force-recreate frigate notifier
```

## Operaciones de WP3 mediante la API

WP3 añade un ciclo explícito de cumplimiento en `control-api`. Todas las operaciones requieren una sesión autenticada y un motivo textual que queda en la auditoría append-only.

```bash
# Confirmar cartelería y encargo de tratamiento
curl -b cookies.txt -X POST https://localhost:8443/api/compliance/confirm \
  -H 'content-type: application/json' \
  -d '{"reason":"Revisión documental completada"}'

# Revocar y activar el kill-switch
curl -b cookies.txt -X POST https://localhost:8443/api/compliance/revoke \
  -H 'content-type: application/json' \
  -d '{"reason":"Se retiró la autorización operativa"}'

# Liberar el kill-switch requiere que ambas confirmaciones estén presentes
curl -b cookies.txt -X POST https://localhost:8443/api/compliance/clear-kill-switch \
  -H 'content-type: application/json' \
  -d '{"reason":"Nueva revisión autorizada"}'
```

La revocación establece ambas confirmaciones a falso y activa el kill-switch. No se puede confirmar mientras el kill-switch permanezca activo, y tampoco se puede liberarlo sin ambas confirmaciones. El renderizador de Frigate sigue siendo fail-closed: mientras `recording_allowed` sea falso, `record.enabled` y `snapshots.enabled` permanecen desactivados.
