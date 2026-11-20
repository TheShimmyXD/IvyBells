// El unico lugar que habla con el Python (web_frontend.md, seccion 5).
import { SseReader } from "./sse";
import type {
  AgentBrief,
  AgentEvent,
  AgentMark,
  AgentMode,
  AgentSnapshot,
  ApiSession,
  ChatBrief,
  ChatEvent,
  ChatSnapshot,
  ListeningEvent,
  ListeningSnapshot,
  Prefs,
  SourceId,
  StartAnswer,
  StatePayload,
  ViewPrefKey,
} from "./types";

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

/** El motivo que la API ya escribe en espanol (``detail`` de FastAPI) o, si no hay, el codigo. */
async function errorFor(response: Response): Promise<ApiError> {
  if (response.status !== 401 && response.status !== 403) {
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        return new ApiError(body.detail);
      }
    } catch {
      // Sin cuerpo JSON: queda el mensaje por codigo.
    }
  }
  return new ApiError(messageForStatus(response.status));
}

function authHeaders(session: ApiSession, init: HeadersInit = {}): Headers {
  const headers = new Headers(init);
  headers.set("Authorization", `Bearer ${session.token}`);
  return headers;
}

async function request<T>(session: ApiSession, path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(session, init.headers);
  const response = await fetch(url(session, path), { ...init, headers });
  if (!response.ok) {
    throw await errorFor(response);
  }
  return (await response.json()) as T;
}

function postJson<T>(session: ApiSession, path: string, body: unknown): Promise<T> {
  return request<T>(session, path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getPrefs(session: ApiSession): Promise<Prefs> {
  return request<Prefs>(session, "/api/prefs");
}

export function savePref(session: ApiSession, key: ViewPrefKey, value: string): Promise<Prefs> {
  return postJson<Prefs>(session, "/api/prefs", { key, value });
}

// -- Escucha en vivo -----------------------------------------------------------------

export const listeningApi = {
  snapshot(session: ApiSession): Promise<ListeningSnapshot> {
    return request<ListeningSnapshot>(session, "/api/listening");
  },
  /** Sin dispositivos: la API usa los recordados si siguen conectados (como Qt). */
  start(session: ApiSession, model: string): Promise<StartAnswer> {
    return postJson<StartAnswer>(session, "/api/listening/start", { model });
  },
  stop(session: ApiSession): Promise<StatePayload> {
    return postJson<StatePayload>(session, "/api/listening/stop", {});
  },
  setSourceOpen(
    session: ApiSession,
    source: SourceId,
    open: boolean,
  ): Promise<{ changed: boolean; closed: SourceId[] }> {
    return postJson(session, `/api/listening/sources/${source}`, { open });
  },
  save(session: ApiSession, path: string): Promise<{ path: string }> {
    return postJson(session, "/api/listening/save", { path });
  },
};

// -- Agente ------------------------------------------------------------------------------

/** La ruta y el cuerpo de una marca; aparte para probar que la web manda lo mismo que Qt. */
export function markRequest(mark: AgentMark): { path: string; body: Omit<AgentMark, "end"> } {
  const path = mark.end ? "/api/agent/mark_end" : "/api/agent/mark_start";
  return { path, body: { phrase: mark.phrase, offset: mark.offset } };
}

export const agentApi = {
  snapshot(session: ApiSession): Promise<AgentSnapshot> {
    return request<AgentSnapshot>(session, "/api/agent");
  },
  mark(session: ApiSession, mark: AgentMark): Promise<AgentBrief> {
    const { path, body } = markRequest(mark);
    return postJson<AgentBrief>(session, path, body);
  },
  /** Cancela el envio en curso o el inicio marcado (Esc). */
  cancel(session: ApiSession): Promise<AgentBrief> {
    return postJson<AgentBrief>(session, "/api/agent/cancel", {});
  },
  setMode(session: ApiSession, mode: AgentMode): Promise<AgentBrief> {
    return postJson<AgentBrief>(session, "/api/agent/mode", { mode });
  },
  setSpeaker(session: ApiSession, source: SourceId): Promise<AgentBrief> {
    return postJson<AgentBrief>(session, "/api/agent/speaker", { source });
  },
};

const AGENT_KINDS = new Set(["state", "turns", "marks", "budget", "mode"]);

/** Un evento del canal del Agente con su tipo; los desconocidos quedan fuera (null). */
export function toAgentEvent(kind: string, data: unknown): AgentEvent | null {
  if (!AGENT_KINDS.has(kind) || typeof data !== "object" || data === null) {
    return null;
  }
  return { kind, data } as AgentEvent;
}

// -- Chat propio del autor -------------------------------------------------------------

export const chatApi = {
  snapshot(session: ApiSession): Promise<ChatSnapshot> {
    return request<ChatSnapshot>(session, "/api/chat");
  },
  /** sent es false si ya hay un envio en curso o el texto queda vacio. */
  send(session: ApiSession, text: string): Promise<ChatBrief & { sent: boolean }> {
    return postJson(session, "/api/chat/send", { text });
  },
  cancel(session: ApiSession): Promise<ChatBrief> {
    return postJson<ChatBrief>(session, "/api/chat/cancel", {});
  },
  /** Vacia el chat; un envio en curso se cancela. */
  clear(session: ApiSession): Promise<ChatBrief> {
    return postJson<ChatBrief>(session, "/api/chat/clear", {});
  },
  setModel(session: ApiSession, model: string): Promise<ChatBrief> {
    return postJson<ChatBrief>(session, "/api/chat/model", { model });
  },
  setEffort(session: ApiSession, effort: string): Promise<ChatBrief> {
    return postJson<ChatBrief>(session, "/api/chat/effort", { effort });
  },
};

const CHAT_KINDS = new Set(["turns", "sending", "config"]);

/** Un evento del canal del chat con su tipo; los desconocidos quedan fuera (null). */
export function toChatEvent(kind: string, data: unknown): ChatEvent | null {
  if (!CHAT_KINDS.has(kind) || typeof data !== "object" || data === null) {
    return null;
  }
  return { kind, data } as ChatEvent;
}

const LISTENING_KINDS = new Set(["state", "phrase", "latency", "session", "sources", "saved"]);

/** Un evento del canal con su tipo; los que esta vista no usa quedan fuera (null). */
export function toListeningEvent(kind: string, data: unknown): ListeningEvent | null {
  if (!LISTENING_KINDS.has(kind) || typeof data !== "object" || data === null) {
    return null;
  }
  return { kind, data } as ListeningEvent;
}

export type EventHandler = (seq: number, kind: string, data: unknown) => void;

/** Lee un canal SSE hasta que la API lo cierra o hasta ``signal``. EventSource no manda
 * Authorization: se lee con fetch. ``after`` pide solo los eventos con numero mayor. */
export async function readEvents(
  session: ApiSession,
  path: string,
  after: number,
  onEvent: EventHandler,
  signal: AbortSignal,
): Promise<void> {
  const headers = authHeaders(session, { Accept: "text/event-stream" });
  if (after > 0) {
    headers.set("Last-Event-ID", String(after));
  }
  const response = await fetch(url(session, path), { headers, signal });
  if (!response.ok) {
    throw await errorFor(response);
  }
  if (response.body === null) {
    throw new ApiError("La API no mandó el canal de eventos.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const sse = new SseReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      return;
    }
    for (const event of sse.push(decoder.decode(value, { stream: true }))) {
      onEvent(event.id ?? 0, event.event, parseData(event.data));
    }
  }
}

function parseData(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}
