// La configuracion de ejemplo para las capturas sin API
// (?demo=1&module=config&account=ok|error|login). Correos y nombres inventados.
import type { AccountStatus, SettingsSnapshot } from "../../api/types";
import { fromSettingsSnapshot, type SettingsView } from "./settingsView";

const ACCOUNTS: Record<string, { account: string; status: AccountStatus }> = {
  ok: {
    account: "persona@example.com",
    status: { text: "Sesión activa · plan pro", level: "ok", login: "" },
  },
  error: {
    account: "persona@example.com",
    status: { text: "«no-correo» no parece un correo", level: "error", login: "" },
  },
  login: {
    account: "otra@example.com",
    status: {
      text: "Sin sesión en esta cuenta",
      level: "warning",
      login:
        "CLAUDE_CONFIG_DIR=~/.local/share/ivybells/claude/otra@example.com claude auth login --email otra@example.com",
    },
  },
};

export const DEMO_SNAPSHOT: SettingsSnapshot = {
  config: {
    model: "haiku",
    effort: "low",
    fallback_model: "",
    timeout_s: 120,
    account: "persona@example.com",
  },
  choices: {
    models: [
      { key: "haiku", label: "haiku", help: "El más barato; primer texto en ~2 s" },
      { key: "sonnet", label: "sonnet", help: "Equilibrado; primer texto en ~2 s" },
      { key: "opus", label: "opus", help: "El más capaz; primer texto en ~3 s" },
    ],
    efforts: [
      { key: "", label: "por defecto", help: "El nivel que trae el modelo" },
      { key: "low", label: "low", help: "Responde más rápido, razona menos" },
      { key: "medium", label: "medium", help: "" },
      { key: "high", label: "high", help: "" },
      { key: "xhigh", label: "xhigh", help: "" },
      { key: "max", label: "max", help: "Razona lo más posible; tarda más" },
    ],
    fallbacks: ["", "haiku", "sonnet", "opus"],
    timeouts_s: [60, 120, 300],
  },
  account: { text: "", level: "", login: "" },
  checking: false,
  profiles: { names: ["ejemplo", "demo soporte", "ventas"], active: "ventas", editable: [] },
  contexts: {
    names: ["empresa", "entrevistas"],
    active: "empresa",
    folder: "contextos/empresa",
    target: "contexto/contexto.md",
    weights: { "precios.csv": 44, "servicios.md": 67 },
    busy: false,
  },
  last_event: 0,
};

export function demoSettings(search: string): SettingsView {
  const stage = new URLSearchParams(search).get("account") ?? "ok";
  const chosen = ACCOUNTS[stage] ?? ACCOUNTS.ok;
  const view = fromSettingsSnapshot(DEMO_SNAPSHOT);
  return {
    ...view,
    config: { ...view.config, account: chosen.account },
    account: chosen.status,
  };
}
