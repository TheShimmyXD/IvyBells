// Estado y pedidos de la vista En vivo: abre con el snapshot de la API, sigue el canal de
// eventos (se reconecta desde el ultimo numero visto) y manda Iniciar, Detener, los
// canales, el modelo y Guardar. Sin sesion (fuera de Tauri) muestra `seed`, si hay.
import { useCallback, useEffect, useState } from "react";
import { listeningApi, savePref, toListeningEvent } from "../../api/client";
import { errorMessage, followChannel } from "../../api/follow";
import type { ApiSession, SourceId } from "../../api/types";
import { applyEvent, fromSnapshot, type LiveView } from "./conversation";

export const EVENTS_PATH = "/api/listening/events";
export const LAST_OPEN_MESSAGE = "Queda al menos un canal abierto.";

export interface LiveListening {
  view: LiveView | null;
  /** Por que fallo el ultimo pedido o el canal; null si todo va bien. */
  error: string | null;
  /** Aviso corto que no es error (por ejemplo, el ultimo canal abierto). */
  notice: string | null;
  model: string;
  chooseModel: (model: string) => void;
  start: () => void;
  stop: () => void;
  toggleSource: (source: SourceId) => void;
  save: (path: string) => void;
}

export function useLiveListening(
  session: ApiSession | null,
  recordedModel: string | null = null,
  seed: LiveView | null = null,
): LiveListening {
  const [view, setView] = useState<LiveView | null>(seed);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);

  useEffect(() => {
    if (session === null) {
      return;
    }
    const abort = new AbortController();
    void followChannel(
      session,
      EVENTS_PATH,
      {
        snapshot: (opened) => listeningApi.snapshot(opened),
        lastEvent: (snapshot) => snapshot.last_event,
        onSnapshot: (snapshot) => setView(fromSnapshot(snapshot)),
        onEvent: (seq, kind, data) => {
          const event = toListeningEvent(kind, data);
          if (event !== null) {
            setView((current) => current && applyEvent(current, seq, event));
          }
        },
        onError: setError,
      },
      abort.signal,
    );
    return () => abort.abort();
  }, [session]);

  // Lo elegido en esta apertura; si no, lo recordado; si no, el de la escucha o el primero.
  const model = chosen ?? recordedModel ?? (view?.model || view?.models.at(-1)?.key || "");

  const run = useCallback(
    <T>(request: (opened: ApiSession) => Promise<T>, then?: (answer: T) => void) => {
      if (session === null) {
        return;
      }
      setError(null);
      setNotice(null);
      request(session)
        .then((answer) => then?.(answer))
        .catch((reason: unknown) => setError(errorMessage(reason)));
    },
    [session],
  );

  const chooseModel = useCallback(
    (next: string) => {
      setChosen(next);
      run((opened) => savePref(opened, "live_model", next));
    },
    [run],
  );

  const start = useCallback(
    () =>
      run(
        (opened) => listeningApi.start(opened, model),
        (answer) => setView((current) => current && { ...current, devices: answer.devices }),
      ),
    [run, model],
  );

  const stop = useCallback(() => run((opened) => listeningApi.stop(opened)), [run]);

  const toggleSource = useCallback(
    (source: SourceId) => {
      const open = view?.closed.includes(source) ?? false;
      run(
        (opened) => listeningApi.setSourceOpen(opened, source, open),
        (answer) => {
          if (!answer.changed && !open) {
            setNotice(LAST_OPEN_MESSAGE);
          }
        },
      );
    },
    [run, view],
  );

  const save = useCallback(
    (path: string) => run((opened) => listeningApi.save(opened, path)),
    [run],
  );

  return { view, error, notice, model, chooseModel, start, stop, toggleSource, save };
}
