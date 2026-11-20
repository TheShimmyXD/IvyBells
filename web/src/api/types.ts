// Tipos de lo que devuelve la API de Python (entrypoints/api/), escritos una sola vez.

/** Puerto y token que entrega la ventana de Tauri (orden api_session de jacck_tauri). */
export interface ApiSession {
  port: number | null;
  token: string;
  error: string | null;
}

export type ThemeName = "light" | "dark";
export type ModuleId = "live" | "agent" | "config";

/** Lo que la interfaz lee al abrirse (GET /api/prefs; SHOWN en entrypoints/api/prefs.py). */
export interface Prefs {
  theme?: string;
  module?: string;
  [key: string]: unknown;
}

/** Las claves que la vista guarda con POST /api/prefs (VIEW_PREFS). */
export type ViewPrefKey = "theme" | "module" | "agent_panel";
