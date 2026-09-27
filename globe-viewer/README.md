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
6. Repite para cada cámara, luego "Exportar cameras.config.js" y pega el resultado en `src/cameras.config.js`.

## Antes de que sea útil de verdad

1. **Rellena `src/cameras.config.js`** con la posición GPS real, el rumbo
   (heading) y el resto de la pose de cada cámara — o mejor, usa la
   herramienta de calibración (`calibrate.html`, ver más arriba) y evítate
   medirlo a mano. Sin esto, el globo se queda centrado en 0,0 y no
   representa nada real — es un placeholder intencionado, no un bug.
2. Confirma que el nombre de cada entrada en `cameras.config.js` coincide
   exactamente con el nombre de la cámara en `../frigate/config.yml`
   (`camara_1`, `camara_2`...), porque así se cruzan los eventos con la
   pose correcta.

## Limitación importante

El punto que "pulsa" en rojo es la **posición de la cámara**, no la posición
real de la persona/vehículo detectado. Frigate no calcula por sí solo dónde
está el objeto en el mundo (para eso haría falta homografía cámara→terreno,
que no está incluida en este MVP). Es una alerta geolocalizada por cámara,
no un tracking de posición real del objeto — suficiente para saber "algo
pasó en la cámara X", no para saber "está a 12 metros al norte del poste".
