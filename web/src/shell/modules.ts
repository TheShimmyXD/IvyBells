// Los modulos de la barra y el tema. La web tiene dos (el Agente vive dentro de En
// vivo); los textos del tema son los que tenia la ventana de Qt.
// Logica pura, sin React.
import type { ModuleId, Prefs, ThemeName } from "../api/types";
import type { IconName } from "../shared/phosphor";

export interface ModuleEntry {
  id: ModuleId;
  label: string;
  icon: IconName;
  tip: string;
}

export const MODULES: readonly ModuleEntry[] = [
  {
    id: "live",
    label: "En vivo",
    icon: "waveform",
    tip: "Ellos y Tú en vivo, con el Agente al lado",
  },
  {
    id: "config",
    label: "Configuración",
    icon: "sliders-horizontal",
    tip: "Cuenta, modelo y esfuerzo de Claude",
  },
];

export const THEME_TIPS: Record<ThemeName, string> = {
  light: "Tema: claro",
  dark: "Tema: oscuro",
};
export const THEME_ICONS: Record<ThemeName, IconName> = { light: "sun", dark: "moon" };

export interface ViewState {
  theme: ThemeName;
  module: ModuleId;
}

export const DEFAULT_VIEW: ViewState = { theme: "light", module: "live" };

function isTheme(value: unknown): value is ThemeName {
  return value === "light" || value === "dark";
}

function isModule(value: unknown): value is ModuleId {
  return MODULES.some((entry) => entry.id === value);
}

/** ?demo=1: En vivo con la llamada de ejemplo, sin API (capturas). */
export function wantsDemo(search: string): boolean {
  return new URLSearchParams(search).has("demo");
}

export function nextTheme(theme: ThemeName): ThemeName {
  return theme === "light" ? "dark" : "light";
}

/** Lo recordado por la API; un valor desconocido queda en el de partida, como en Qt. */
export function viewFromPrefs(prefs: Prefs, base: ViewState = DEFAULT_VIEW): ViewState {
  return {
    theme: isTheme(prefs.theme) ? prefs.theme : base.theme,
    module: isModule(prefs.module) ? prefs.module : base.module,
  };
}

/** Fuera de Tauri no hay API: ?theme=dark&module=config sirve para las capturas. */
export function viewFromQuery(search: string): ViewState {
  const params = new URLSearchParams(search);
  return viewFromPrefs({
    theme: params.get("theme") ?? undefined,
    module: params.get("module") ?? undefined,
  });
}
