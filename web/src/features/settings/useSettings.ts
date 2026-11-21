// Estado y pedidos de la configuracion de Claude: abre con el snapshot de /api/settings,
// sigue su canal de eventos y manda cada cambio, que la API guarda al momento en
// app_settings.json.
import { useCallback, useEffect, useState } from "react";
import { ApiError, settingsApi, toSettingsEvent } from "../../api/client";
import { errorMessage, followChannel } from "../../api/follow";
import type { ApiSession, ContextsData, ProfilesData, SettingsConfig } from "../../api/types";
import { profilesOnly } from "./profileView";
import { applySettingsEvent, fromSettingsSnapshot, type SettingsView } from "./settingsView";

export const SETTINGS_EVENTS_PATH = "/api/settings/events";

export interface Settings {
  view: SettingsView | null;
  /** Por que fallo el ultimo pedido o el canal; null si todo va bien. */
  error: string | null;
  setModel: (model: string) => void;
  setEffort: (effort: string) => void;
  setFallback: (model: string) => void;
  setTimeout: (seconds: number) => void;
  /** Guarda el correo y lo comprueba; si no parece un correo, lo dice la insignia. */
  setAccount: (account: string) => void;
  check: () => void;
  /** Pone la lista de perfiles que respondio un pedido, sin esperar al canal. */
  applyProfiles: (profiles: ProfilesData) => void;
  /** Pone la lista de contextos que respondio un pedido, sin esperar al canal. */
  applyContexts: (contexts: ContextsData) => void;
}

/** `seed`: la configuracion de ejemplo sin API (capturas con ?demo=1&module=config). */
export function useSettings(
  session: ApiSession | null,
  seed: SettingsView | null = null,
): Settings {
  const [view, setView] = useState<SettingsView | null>(seed);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session === null) {
      return;
    }
    const abort = new AbortController();
    void followChannel(
      session,
      SETTINGS_EVENTS_PATH,
      {
        snapshot: (opened) => settingsApi.snapshot(opened),
        lastEvent: (snapshot) => snapshot.last_event,
        onSnapshot: (snapshot) => setView(fromSettingsSnapshot(snapshot)),
        onEvent: (seq, kind, data) => {
          const event = toSettingsEvent(kind, data);
          if (event !== null) {
            setView((current) => current && applySettingsEvent(current, seq, event));
          }
        },
        onError: setError,
      },
      abort.signal,
    );
    return () => abort.abort();
  }, [session]);

  const run = useCallback(
    (request: (opened: ApiSession) => Promise<SettingsConfig>, quietStatus = 0) => {
      if (session === null) {
        return;
      }
      setError(null);
      request(session)
        .then((config) => setView((current) => current && { ...current, config }))
        .catch((reason: unknown) => {
          // El motivo de ese codigo ya llega por el canal (la insignia de la cuenta).
          if (!(reason instanceof ApiError && reason.status === quietStatus)) {
            setError(errorMessage(reason));
          }
        });
    },
    [session],
  );

  const setModel = useCallback(
    (model: string) => run((opened) => settingsApi.setModel(opened, model)),
    [run],
  );
  const setEffort = useCallback(
    (effort: string) => run((opened) => settingsApi.setEffort(opened, effort)),
    [run],
  );
  const setFallback = useCallback(
    (model: string) => run((opened) => settingsApi.setFallback(opened, model)),
    [run],
  );
  const setTimeout = useCallback(
    (seconds: number) => run((opened) => settingsApi.setTimeout(opened, seconds)),
    [run],
  );
  const setAccount = useCallback(
    (account: string) => run((opened) => settingsApi.setAccount(opened, account), 422),
    [run],
  );
  const check = useCallback(() => {
    if (session === null) {
      return;
    }
    setError(null);
    settingsApi.check(session).catch((reason: unknown) => setError(errorMessage(reason)));
  }, [session]);

  const applyProfiles = useCallback((profiles: ProfilesData) => {
    setView((current) => current && { ...current, profiles: profilesOnly(profiles) });
  }, []);

  const applyContexts = useCallback((contexts: ContextsData) => {
    setView((current) => current && { ...current, contexts });
  }, []);

  return {
    view,
    error,
    setModel,
    setEffort,
    setFallback,
    setTimeout,
    setAccount,
    check,
    applyProfiles,
    applyContexts,
  };
}
