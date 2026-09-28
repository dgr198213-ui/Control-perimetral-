import { defineConfig } from "vite";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  plugins: [cesium()],
  build: {
    rollupOptions: {
      input: {
        main: "index.html",
        calibrate: "calibrate.html",
      },
    },
  },
  server: {
    host: "127.0.0.1", // solo local, coherente con el resto del stack — no exponer a internet
    port: 5173,
    proxy: {
      // Evita problemas de CORS al llamar a la API de Frigate desde el navegador.
      // Ajusta el target si Frigate corre en otra IP de tu red local.
      "/frigate-api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/frigate-api/, ""),
      },
    },
  },
});
