// La configuracion de Claude como datos: el estado que arma el snapshot de /api/settings,
// cada evento de su canal y los textos de la pestana Claude. Logica pura, sin React.
import type {
  AccountLevel,
  AccountStatus,
  ContextNotice,
  ContextsData,
  ProfilesData,
  SettingsChoices,
  SettingsConfig,
  SettingsEvent,
  SettingsSnapshot,
} from "../../api/types";

export interface SettingsView {
  config: SettingsConfig;
  choices: SettingsChoices;
  account: AccountStatus;
  profiles: ProfilesData;
  contexts: ContextsData;
  /** El ultimo aviso de la foto contexto.md (leyendo, resumen o error). */
  contextNotice: ContextNotice;
  lastEvent: number;
}

const CHECKING: AccountStatus = { text: "Comprobando la cuenta...", level: "busy", login: "" };

export function fromSettingsSnapshot(snapshot: SettingsSnapshot): SettingsView {
  const { config, choices, profiles, contexts } = snapshot;
  // Si la comprobacion sigue en curso, la ultima cuenta avisada aun no es la de ahora.
  const account = snapshot.checking ? CHECKING : snapshot.account;
  return {
    config,
    choices,
    account,
    profiles,
    contexts,
    contextNotice: snapshot.context_notice,
    lastEvent: snapshot.last_event,
  };
}

export function applySettingsEvent(
  view: SettingsView,
  seq: number,
  event: SettingsEvent,
): SettingsView {
  const next = { ...view, lastEvent: Math.max(view.lastEvent, seq) };
  switch (event.kind) {
    case "config":
      return { ...next, config: event.data };
    case "account":
      return { ...next, account: event.data };
    case "profiles":
      return { ...next, profiles: event.data };
    case "contexts":
      return { ...next, contexts: event.data };
    case "context_reloaded":
      return { ...next, contextNotice: event.data };
  }
}

export type BadgeTone = "info" | "ok" | "warning" | "error";

export interface AccountBadge {
  text: string;
  tone: BadgeTone;
  busy: boolean;
}

const LEVEL_TONES: Record<AccountLevel, BadgeTone> = {
  "": "info",
  info: "info",
  busy: "info",
  ok: "ok",
  warning: "warning",
  error: "error",
};

/** La insignia de la cuenta: el texto que aviso la API o "Sin comprobar". */
export function accountBadge(status: AccountStatus): AccountBadge {
  return {
    text: status.text || "Sin comprobar",
    tone: LEVEL_TONES[status.level] ?? "info",
    busy: status.level === "busy",
  };
}

/** La letra del circulo: la inicial del correo, o "?" con la sesion de siempre. */
export function accountInitial(account: string): string {
  const first = account.trim().charAt(0);
  return first === "" ? "?" : first.toUpperCase();
}

/** Lo que se escribio difiere de lo guardado (mismo criterio que Qt: sin espacios ni mayusculas). */
export function accountChanged(typed: string, saved: string): boolean {
  return typed.trim().toLowerCase() !== saved;
}

const MORE_EFFORT_HELP = "Más esfuerzo tarda más en dar el primer texto";

/** La ayuda junto a "Esfuerzo": la del nivel elegido o, si no trae, la general. */
export function effortHelp(choices: SettingsChoices, effort: string): string {
  const chosen = choices.efforts.find((entry) => entry.key === effort);
  return chosen?.help || MORE_EFFORT_HELP;
}

/** El respaldo como se lee en la lista: "" es ninguno. */
export function fallbackLabel(key: string): string {
  return key === "" ? "ninguno" : key;
}

export function timeoutLabel(seconds: number): string {
  return `${seconds} s`;
}
