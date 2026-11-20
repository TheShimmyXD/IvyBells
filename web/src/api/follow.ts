// Seguir un canal de la API: abre con su snapshot y lee sus eventos; si el canal se corta,
// vuelve a leer desde el ultimo numero visto. Lo usan el Agente y el chat.
import { readEvents } from "./client";
import type { ApiSession } from "./types";

const RETRY_MS = 1_000;

export interface Follower<S> {
  snapshot: (session: ApiSession) => Promise<S>;
  /** El numero del ultimo evento que el snapshot ya refleja. */
  lastEvent: (snapshot: S) => number;
  onSnapshot: (snapshot: S) => void;
  /** Solo eventos nuevos: los repetidos tras reconectar no llegan. */
  onEvent: (seq: number, kind: string, data: unknown) => void;
  onError: (message: string) => void;
}

export function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Sigue el canal hasta ``signal``; los errores llegan a ``onError`` y no cortan el bucle. */
export async function followChannel<S>(
  session: ApiSession,
  path: string,
  follower: Follower<S>,
  signal: AbortSignal,
  retryMs = RETRY_MS,
): Promise<void> {
  let last: number;
  try {
    const snapshot = await follower.snapshot(session);
    if (signal.aborted) {
      return;
    }
    last = follower.lastEvent(snapshot);
    follower.onSnapshot(snapshot);
  } catch (reason) {
    if (!signal.aborted) {
      follower.onError(errorMessage(reason));
    }
    return;
  }
  const onEvent = (seq: number, kind: string, data: unknown) => {
    if (seq > 0 && seq <= last) {
      return;
    }
    last = Math.max(last, seq);
    follower.onEvent(seq, kind, data);
  };
  while (!signal.aborted) {
    try {
      await readEvents(session, path, last, onEvent, signal);
    } catch (reason) {
      if (!signal.aborted) {
        follower.onError(errorMessage(reason));
      }
    }
    if (!signal.aborted) {
      await wait(retryMs);
    }
  }
}
