// Textos y estados de la vista En vivo que no dependen de React: latencia, ruta del .md y
// que hace el boton principal en cada estado (los mismos de domain/transcription).
import type { LatencyPayload, ListeningStateName } from "../../api/types";

export type RunAction = "start" | "stop" | "wait";
export type StateTone = "idle" | "busy" | "ok" | "error";

/** Segundos con coma decimal, como format_latency de Python; sin dato, un guion. */
export function formatSeconds(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1).replace(".", ",")} s`;
}

export function latencyParts(latency: LatencyPayload): { last: string; median: string } {
  return { last: formatSeconds(latency.last_s), median: formatSeconds(latency.median_s) };
}

/** La carpeta y el archivo (el resto, en la ayuda): transcripciones/2026-11-19_2008.md. */
export function shortPath(path: string): string {
  const parts = path.split(/[\\/]/).filter((part) => part !== "");
  return parts.slice(-2).join("/");
}

/** can_start y can_stop de LiveLogic. */
export function runAction(state: ListeningStateName): RunAction {
  if (state === "stopped" || state === "error") {
    return "start";
  }
  return state === "stopping" ? "wait" : "stop";
}

export function stateTone(state: ListeningStateName): StateTone {
  switch (state) {
    case "listening":
      return "ok";
    case "error":
      return "error";
    case "stopped":
      return "idle";
    default:
      return "busy";
  }
}
