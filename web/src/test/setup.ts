// Comparadores de Testing Library para Vitest y limpieza del DOM entre pruebas. La red no
// se usa nunca: un ``fetch`` sin simular falla (web_frontend.md, seccion 6).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

vi.stubGlobal(
  "fetch",
  vi.fn(() => Promise.reject(new Error("Las pruebas no usan la red: simula la API."))),
);

afterEach(() => {
  cleanup();
});
