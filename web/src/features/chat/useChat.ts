// Estado y pedidos del chat propio del autor: abre con el snapshot de /api/chat, sigue su
// canal de eventos y manda los envios, cancelar, vaciar, el modelo y el esfuerzo.
import { useCallback, useEffect, useState } from "react";
import { chatApi, toChatEvent } from "../../api/client";
import { errorMessage, followChannel } from "../../api/follow";
import type { ApiSession, ChatBrief } from "../../api/types";
import { applyChatEvent, fromChatSnapshot, sendable, type ChatView } from "./chatView";

export const CHAT_EVENTS_PATH = "/api/chat/events";

export interface Chat {
  view: ChatView | null;
  /** Por que fallo el ultimo pedido o el canal; null si todo va bien. */
  error: string | null;
  /** true si la API acepto el envio (el cuadro se vacia entonces). */
  send: (text: string) => Promise<boolean>;
  cancel: () => void;
  clear: () => void;
  setModel: (model: string) => void;
  setEffort: (effort: string) => void;
}

/** `seed`: el chat de ejemplo sin API (capturas con ?demo=1&chat=...). */
export function useChat(session: ApiSession | null, seed: ChatView | null = null): Chat {
  const [view, setView] = useState<ChatView | null>(seed);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session === null) {
      return;
    }
    const abort = new AbortController();
    void followChannel(
      session,
      CHAT_EVENTS_PATH,
      {
        snapshot: (opened) => chatApi.snapshot(opened),
        lastEvent: (snapshot) => snapshot.last_event,
        onSnapshot: (snapshot) => setView(fromChatSnapshot(snapshot)),
        onEvent: (seq, kind, data) => {
          const event = toChatEvent(kind, data);
          if (event !== null) {
            setView((current) => current && applyChatEvent(current, seq, event));
          }
        },
        onError: setError,
      },
      abort.signal,
    );
    return () => abort.abort();
  }, [session]);

  const merge = useCallback((brief: ChatBrief) => {
    const { model, effort, sending } = brief;
    setView((current) => current && { ...current, model, effort, sending });
  }, []);

  const run = useCallback(
    (request: (opened: ApiSession) => Promise<ChatBrief>) => {
      if (session === null) {
        return;
      }
      setError(null);
      request(session)
        .then(merge)
        .catch((reason: unknown) => setError(errorMessage(reason)));
    },
    [session, merge],
  );

  const send = useCallback(
    async (text: string) => {
      const request = sendable(view, text);
      if (session === null || request === null) {
        return false;
      }
      setError(null);
      try {
        const answer = await chatApi.send(session, request);
        merge(answer);
        return answer.sent;
      } catch (reason) {
        setError(errorMessage(reason));
        return false;
      }
    },
    [session, view, merge],
  );
  const cancel = useCallback(() => run((opened) => chatApi.cancel(opened)), [run]);
  const clear = useCallback(() => run((opened) => chatApi.clear(opened)), [run]);
  const setModel = useCallback(
    (model: string) => run((opened) => chatApi.setModel(opened, model)),
    [run],
  );
  const setEffort = useCallback(
    (effort: string) => run((opened) => chatApi.setEffort(opened, effort)),
    [run],
  );

  return { view, error, send, cancel, clear, setModel, setEffort };
}
