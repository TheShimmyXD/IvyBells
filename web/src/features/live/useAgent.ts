// Estado y pedidos del Agente en la vista En vivo: abre con el snapshot de /api/agent,
// sigue su canal de eventos (followChannel: se reconecta desde el ultimo numero visto) y manda las marcas
// de los clics, cancelar, el modo y el interlocutor.
import { useCallback, useEffect, useState } from "react";
import { agentApi, toAgentEvent } from "../../api/client";
import { errorMessage, followChannel } from "../../api/follow";
import type { AgentBrief, AgentMode, ApiSession, SourceId } from "../../api/types";
import { markFor, type MarkButton } from "./agentMarks";
import { applyAgentEvent, fromAgentSnapshot, type AgentView } from "./agentView";
import type { Bubble } from "./conversation";

export const AGENT_EVENTS_PATH = "/api/agent/events";

export interface Agent {
  view: AgentView | null;
  /** Por que fallo el ultimo pedido o el canal; null si todo va bien. */
  error: string | null;
  /** Clic sobre una burbuja: solo cuenta en las frases finales del interlocutor. */
  mark: (bubble: Bubble, button: MarkButton) => void;
  cancel: () => void;
  setMode: (mode: AgentMode) => void;
  setSpeaker: (source: SourceId) => void;
}

/** `seed`: el Agente de ejemplo sin API (capturas con ?demo=1&agent=...). */
export function useAgent(session: ApiSession | null, seed: AgentView | null = null): Agent {
  const [view, setView] = useState<AgentView | null>(seed);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session === null) {
      return;
    }
    const abort = new AbortController();
    void followChannel(
      session,
      AGENT_EVENTS_PATH,
      {
        snapshot: (opened) => agentApi.snapshot(opened),
        lastEvent: (snapshot) => snapshot.last_event,
        onSnapshot: (snapshot) => setView(fromAgentSnapshot(snapshot)),
        onEvent: (seq, kind, data) => {
          const event = toAgentEvent(kind, data);
          if (event !== null) {
            setView((current) => current && applyAgentEvent(current, seq, event));
          }
        },
        onError: setError,
      },
      abort.signal,
    );
    return () => abort.abort();
  }, [session]);

  const run = useCallback(
    (request: (opened: ApiSession) => Promise<AgentBrief>) => {
      if (session === null) {
        return;
      }
      setError(null);
      request(session)
        .then((brief) => setView((current) => current && { ...current, ...brief }))
        .catch((reason: unknown) => setError(errorMessage(reason)));
    },
    [session],
  );

  const speaker = view?.speaker;
  const mark = useCallback(
    (bubble: Bubble, button: MarkButton) => {
      const found = speaker === undefined ? null : markFor(bubble, speaker, button);
      if (found !== null) {
        run((opened) => agentApi.mark(opened, found));
      }
    },
    [run, speaker],
  );
  const cancel = useCallback(() => run((opened) => agentApi.cancel(opened)), [run]);
  const setMode = useCallback(
    (mode: AgentMode) => run((opened) => agentApi.setMode(opened, mode)),
    [run],
  );
  const setSpeaker = useCallback(
    (source: SourceId) => run((opened) => agentApi.setSpeaker(opened, source)),
    [run],
  );

  return { view, error, mark, cancel, setMode, setSpeaker };
}
