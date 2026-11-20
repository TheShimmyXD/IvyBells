// El unico lugar que habla con el Python (web_frontend.md, seccion 5).
import type { ApiSession, Prefs, ViewPrefKey } from "./types";

/** Un error de la API, ya en espanol para la pantalla. */
export class ApiError extends Error {}

const STATUS_MESSAGES: Record<number, string> = {
  401: "La API rechazó el token de esta sesión.",
  403: "La API rechazó el origen de la ventana.",
};

export function messageForStatus(status: number): string {
  return STATUS_MESSAGES[status] ?? `La API respondió con el código ${status}.`;
}

function url(session: ApiSession, path: string): string {
  if (session.port === null) {
    throw new ApiError(session.error ?? "La API de Python no está lista.");
  }
  return `http://127.0.0.1:${session.port}${path}`;
}

async function request<T>(session: ApiSession, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.token}`);
  const response = await fetch(url(session, path), { ...init, headers });
  if (!response.ok) {
    throw new ApiError(messageForStatus(response.status));
  }
  return (await response.json()) as T;
}

export function getPrefs(session: ApiSession): Promise<Prefs> {
  return request<Prefs>(session, "/api/prefs");
}

export function savePref(session: ApiSession, key: ViewPrefKey, value: string): Promise<Prefs> {
  return request<Prefs>(session, "/api/prefs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, value }),
  });
}
