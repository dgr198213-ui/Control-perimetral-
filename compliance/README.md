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
