// Vite sirve la interfaz; Vitest corre las pruebas con la misma configuracion.
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // Solo la maquina local, igual que la API de IvyBells.
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    fs: {
      // Letras e iconos de resources/ (una sola copia, con sus licencias).
      allow: [
        fileURLToPath(new URL(".", import.meta.url)),
        fileURLToPath(new URL("../resources/fonts", import.meta.url)),
        fileURLToPath(new URL("../resources/icons", import.meta.url)),
      ],
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Sin aislar cada archivo, jsdom no se crea una vez por archivo: 1,6 s en vez de
    // 3,3 s. Las pruebas pasan tambien en orden aleatorio (--sequence.shuffle).
    // vmThreads era la otra opcion, pero ahi no existe ReadableStream (canal SSE).
    isolate: false,
  },
});
