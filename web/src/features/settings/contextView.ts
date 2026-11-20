// La pestana Contexto como datos: la lista (con "Sin contexto" primero), la barra con el
// peso de cada archivo en contexto.md y el aviso de la foto. Logica pura, sin React; los
// tokens llegan estimados de la API (los mismos que muestra Qt).
import type { ContextEntry, ContextNotice, ContextsData } from "../../api/types";
import { thousands } from "../../shared/format";
import type { BadgeTone } from "./settingsView";

export const NO_CONTEXT = "Sin contexto";

export interface ContextRow {
  /** "" es Sin contexto. */
  name: string;
  label: string;
  active: boolean;
}

export function contextRows(contexts: ContextsData): ContextRow[] {
  const none = { name: "", label: NO_CONTEXT, active: contexts.active === "" };
  return [
    none,
    ...contexts.names.map((name) => ({ name, label: name, active: name === contexts.active })),
  ];
}

export interface WeightPart extends ContextEntry {
  /** Porcentaje de la barra (0 a 100). */
  share: number;
  /** Color alterno de la barra y del punto de su fila. */
  tone: "first" | "second";
}

export interface WeightBar {
  parts: WeightPart[];
  total: number;
}

export function weightBar(entries: ContextEntry[]): WeightBar {
  const total = entries.reduce((sum, entry) => sum + entry.tokens, 0);
  const parts = entries.map((entry, index) => ({
    ...entry,
    share: total === 0 ? 0 : (100 * entry.tokens) / total,
    tone: index % 2 === 0 ? ("first" as const) : ("second" as const),
  }));
  return { parts, total };
}

/** "~1.200 tokens"; un archivo que no aporta nada dice por que puede ser. */
export function tokensLabel(tokens: number): string {
  return tokens === 0 ? "0 (sin leer o vacío)" : `~${thousands(tokens)} tokens`;
}

/** Las dos ultimas partes de la carpeta: ".../resources/agent/contextos/x" -> "contextos/x". */
export function shortFolder(folder: string | null): string {
  if (folder === null) {
    return "";
  }
  return folder.split(/[\\/]/).filter(Boolean).slice(-2).join("/");
}

const NOTICE_TONES: Record<ContextNotice["level"], BadgeTone> = {
  "": "info",
  busy: "info",
  info: "info",
  ok: "ok",
  warning: "warning",
  error: "error",
};

export function noticeTone(notice: ContextNotice): BadgeTone {
  return NOTICE_TONES[notice.level] ?? "info";
}

/** Leyendo si la API lo dice en la lista o en el ultimo aviso. */
export function isReloading(contexts: ContextsData, notice: ContextNotice): boolean {
  return contexts.busy || notice.level === "busy";
}
