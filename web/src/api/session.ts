// Puerto y token de la API que lanza la ventana de Tauri (jacck_tauri).
import { invoke, isTauri } from "@tauri-apps/api/core";
import type { ApiSession } from "./types";

export type SessionReader = () => Promise<ApiSession>;
export type Sleep = (ms: number) => Promise<void>;

export const SESSION_RETRY_MS = 200;
export const SESSION_TIMEOUT_MS = 30_000;
export const SESSION_TIMEOUT_MESSAGE = "La API de Python no anunció su puerto en 30 s.";

export const readDesktopSession: SessionReader = () => invoke<ApiSession>("api_session");

const delay: Sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Fuera de Tauri (npm run dev en el navegador) no hay API lanzada. */
export function runsInDesktop(): boolean {
  return isTauri();
}

/** Pregunta a Tauri hasta que el Python anuncie su puerto o diga su error. */
export async function waitForSession(
  read: SessionReader = readDesktopSession,
  sleep: Sleep = delay,
  attempts: number = SESSION_TIMEOUT_MS / SESSION_RETRY_MS,
): Promise<ApiSession> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const session = await read();
    if (session.port !== null || session.error !== null) {
      return session;
    }
    await sleep(SESSION_RETRY_MS);
  }
  return { port: null, token: "", error: SESSION_TIMEOUT_MESSAGE };
}
