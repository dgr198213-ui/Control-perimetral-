# Aviso de origen — código de terceros reutilizado

`src/viewshed.js` contiene funciones adaptadas de **God's Eye View**
(https://github.com/bilawalsidhu/gods-eye-view), publicado bajo licencia MIT:

```
MIT License
Copyright (c) 2026 Bilawal Sidhu
```

Ficheros de origen (dentro del repo de God's Eye View):
- `src/data/cctvFootprint.js` → funciones `projectPoint`, `planeDimensions`
- `src/data/cctvViewshed.js` → función `createFrustumVolumePrimitive`
- `src/layers/cctv/geometry.js` → estructura de `computeFrustumGeometry`

Se han simplificado deliberadamente (sin muestreo de terreno/DEM, sin
integración con Google 3D Tiles, sin calibración interactiva por arrastre)
para un uso personal de un único perímetro fijo. La licencia MIT original se
mantiene íntegra en este aviso, tal y como exige su condición de atribución.

El resto del proyecto (`main.js`, `frigateBridge.js`, `cameras.config.js`,
integración con Frigate) es código propio, sin relación con God's Eye View.
