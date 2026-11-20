// La configuracion de ejemplo para las capturas sin API
// (?demo=1&module=config&account=ok|error|login&tab=profile&profile=<nombre>). Correos,
// nombres y textos inventados.
import type { AccountStatus, SettingsSnapshot } from "../../api/types";
import { fromSettingsSnapshot, type SettingsView } from "./settingsView";
import type { ProfileSeed } from "./useProfiles";

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
  profiles: {
    names: ["ejemplo", "demo soporte", "ventas"],
    active: "ventas",
    editable: ["demo soporte", "ventas"],
  },
  contexts: {
    names: ["empresa", "entrevistas"],
    active: "empresa",
    folder: "contextos/empresa",
    target: "contexto/contexto.md",
    weights: { "precios.csv": 44, "servicios.md": 67 },
    entries: [
      { name: "precios.csv", tokens: 44, folder: false },
      { name: "servicios.md", tokens: 67, folder: false },
    ],
    busy: false,
  },
  context_notice: { text: "contexto.md: 2 archivos, 444 caracteres", level: "ok" },
  last_event: 0,
};

// Un contexto grande inventado (&files=many): pesos desiguales, uno minimo y uno vacio.
const MANY_FILES: [string, number][] = [
  ["00_presentacion.md", 4675],
  ["01_historia_de_la_empresa.md", 4953],
  ["02_catalogo_de_servicios.md", 12402],
  ["03_precios_2026.csv", 2310],
  ["04_preguntas_frecuentes.md", 7926],
  ["05_politica_de_garantia.pdf", 7100],
  ["06_manual_de_soporte.docx", 9936],
  ["07_casos_de_exito.md", 3669],
  ["08_glosario.md", 627],
  ["09_contratos_tipo.pdf", 8098],
  ["10_horarios.txt", 81],
  ["11_organigrama.md", 1581],
  ["12_objeciones_comunes.md", 5406],
  ["13_notas_vacias.md", 0],
];

export function demoSettings(search: string): SettingsView {
  const query = new URLSearchParams(search);
  const stage = query.get("account") ?? "ok";
  const chosen = ACCOUNTS[stage] ?? ACCOUNTS.ok;
  const view = fromSettingsSnapshot(DEMO_SNAPSHOT);
  const contexts =
    query.get("files") === "many"
      ? {
          ...view.contexts,
          entries: MANY_FILES.map(([name, tokens]) => ({ name, tokens, folder: false })),
        }
      : view.contexts;
  return {
    ...view,
    contexts,
    config: { ...view.config, account: chosen.account },
    account: chosen.status,
  };
}

const PROFILE_TEXTS: Record<string, string> = {
  ejemplo: "Eres el asistente de una empresa de ejemplo.\n\nResponde en dos o tres frases cortas.",
  "demo soporte": [
    "Eres el asistente de soporte técnico de una empresa de ejemplo.",
    "",
    "Cómo respondes:",
    "- Con calma y en frases cortas: la respuesta se lee en voz alta.",
    "- Primero confirmas qué entendiste del problema y luego das un solo paso a seguir.",
    "",
    "Datos de la empresa:",
    "- Soporte de lunes a sábado, de 7:00 a 20:00.",
  ].join("\n"),
  ventas: "Eres el asistente de ventas de una empresa de ejemplo.\n\nNo prometas precios.",
};

export type DemoSettingsTab = "claude" | "profile" | "context";

/** La pestana que abre la captura (&tab=profile|context); Claude si no se pide otra. */
export function demoSettingsTab(search: string): DemoSettingsTab {
  const tab = new URLSearchParams(search).get("tab");
  return tab === "profile" || tab === "context" ? tab : "claude";
}

export function demoProfiles(search: string): ProfileSeed {
  return { selected: new URLSearchParams(search).get("profile"), texts: PROFILE_TEXTS };
}
