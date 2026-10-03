# Visor 3D del perímetro

Globo 3D local (Cesium) que muestra tus cámaras, su cono de cobertura real
(viewshed) y pulsa en rojo cuando Frigate detecta persona/vehículo. Sin
cuentas, sin claves de pago, sin nube — todo corre en tu máquina.

Ver `THIRD-PARTY-NOTICE.md` para el origen del código de viewshed (adaptado
de God's Eye View, MIT).

## Requisitos previos

El stack de Frigate (ver carpeta `../` del proyecto) debe estar corriendo,
con el dashboard accesible en `http://127.0.0.1:5000`.

## Puesta en marcha

```bash
cd globe-viewer
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`.

## Calibrar tus cámaras (recomendado, en vez de medir a mano)

```bash
npm run dev
```

Abre `http://127.0.0.1:5173/calibrate.html`.

1. Busca tu finca con el buscador (aquí sí hay geocoder, a diferencia del visor principal).
2. Click en el mapa donde está la cámara físicamente.
3. Click en el mapa hacia donde apunta — el heading se calcula solo, no hace falta brújula.
4. Ajusta pitch/FOV/alcance/altura con los sliders mientras ves el cono de cobertura en tiempo real.
5. Ponle el mismo `id` que tiene en `frigate/config.yml` y pulsa "Guardar cámara".
6. Repite para cada cámara, luego "Exportar cameras.config.js" y guarda el resultado localmente en `src/cameras.config.js` (este archivo está excluido de Git).

## Antes de que sea útil de verdad

1. **Crea localmente y rellena `src/cameras.config.js`** con la posición GPS real, el rumbo
   (heading) y el resto de la pose de cada cámara — o mejor, usa la
   herramienta de calibración (`calibrate.html`, ver más arriba) y evítate
   medirlo a mano. Sin esto, el globo se queda centrado en 0,0 y no
   representa nada real — es un placeholder intencionado, no un bug.
2. Confirma que el nombre de cada entrada en `cameras.config.js` coincide
   exactamente con el nombre de la cámara en `../frigate/config.yml`
   (`camara_1`, `camara_2`...), porque así se cruzan los eventos con la
   pose correcta.

## Build y despliegue estático

Para Vercel, configura `globe-viewer` como **Root Directory** y usa el comando `npm run build`. La salida será `dist/`, con `index.html` y `calibrate.html`.

## Limitación importante

El punto que "pulsa" en rojo es la **posición de la cámara**, no la posición
real de la persona/vehículo detectado. Frigate no calcula por sí solo dónde
está el objeto en el mundo (para eso haría falta homografía cámara→terreno,
que no está incluida en este MVP). Es una alerta geolocalizada por cámara,
no un tracking de posición real del objeto — suficiente para saber "algo
pasó en la cámara X", no para saber "está a 12 metros al norte del poste".


## Integración multisensor en tiempo real

El visor consulta la API HTTP de solo lectura mediante el proxy local `/multisensor-api`, que apunta a `http://127.0.0.1:8000`. El navegador no se conecta directamente a MQTT y no decide si existe una intrusión: representa los contratos ya producidos por el núcleo.

| Capa | Representación |
|---|---|
| `camera` | Punto naranja asociado a la ubicación del contrato `Observation`; Frigate mantiene además el pulso rojo de la cámara configurada. |
| `pir` | Punto amarillo en la ubicación canónica del sensor. |
| `Incident` | Punto rojo de mayor tamaño con etiqueta, score, estado, `evidence_ids` y explicación. |

`multisensorBridge.js` realiza polling cada tres segundos de `/api/multisensor/observations` e `/api/multisensor/incidents`, a través del proxy Vite, y deduplica por ID. `multisensorLayers.js` convierte las entidades con ubicación válida en objetos Cesium y conserva descripciones seleccionables. Los eventos sin ubicación no se dibujan en el mapa, pero no se convierten artificialmente en coordenadas.

Para disponer de datos multisensor durante el desarrollo hay que iniciar por separado la API HTTP del núcleo y el visor:

```bash
# Terminal 1, desde la raíz
python3 -m multisensor.api.app

# Terminal 2
cd globe-viewer
npm install
npm run dev
```

La integración visual no sustituye la configuración de `src/cameras.config.js`: para Frigate, el pulso sigue representando la posición de la cámara y no la posición exacta del objeto detectado. Del mismo modo, una observación o incidente solo aparece geolocalizado si el contrato del backend incluye `location` válida. Cesium no envía Telegram, no publica webhooks y no aplica el Policy Engine.

## Capa satelital y límites de uso

El visor usa Esri World Imagery como **contexto cartográfico**. No es vídeo en directo: la fecha de adquisición y la actualización dependen del proveedor, y la interfaz lo indica explícitamente. El visor no integra cámaras públicas de tráfico, catálogos DGT ni fuentes externas de seguimiento.

La cartografía conserva atribución visible. No se deben usar las teselas estándar de OpenStreetMap como un servicio ilimitado: sus servidores requieren URL HTTPS, atribución, identificación y cacheo respetuoso [1]. La capa oficial española PNOA/IGN puede configurarse posteriormente mediante WMTS [2].

### Fuentes

[1]: https://operations.osmfoundation.org/policies/tiles/ "OpenStreetMap Tile Usage Policy"
[2]: https://data.europa.eu/data/datasets/spaignwmts_pnoa-ma?locale=en "WMTS of Orthoimages of Spain — PNOA and Sentinel-2"
