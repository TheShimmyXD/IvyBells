// Vite sirve la interfaz; Vitest corre las pruebas con la misma configuracion.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // Solo la maquina local, igual que la API de IvyBells.
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
