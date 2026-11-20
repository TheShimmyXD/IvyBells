// Tema y modulo de la ventana: se leen de la API al abrir y se guardan al cambiar, como
// en Qt (app_settings.json). Fuera de Tauri se leen de la URL y no se guardan.
import { useCallback, useEffect, useRef, useState } from "react";
import { getPrefs, savePref } from "../api/client";
import { runsInDesktop, waitForSession } from "../api/session";
import type { ApiSession, ModuleId, ViewPrefKey } from "../api/types";
import { nextTheme, viewFromPrefs, viewFromQuery, type ViewState } from "./modules";

export interface ViewPrefs extends ViewState {
  /** Por que la API no respondio; null si todo va bien. */
  error: string | null;
  chooseModule: (module: ModuleId) => void;
  cycleTheme: () => void;
}

function message(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

export function useViewPrefs(
  desktop: boolean = runsInDesktop(),
  connect: () => Promise<ApiSession> = waitForSession,
): ViewPrefs {
  const [view, setView] = useState<ViewState>(() => viewFromQuery(window.location.search));
  const [error, setError] = useState<string | null>(null);
  const session = useRef<ApiSession | null>(null);

  useEffect(() => {
    if (!desktop) {
      return;
    }
    let alive = true;
    connect()
      .then(async (opened) => {
        if (opened.port === null) {
          throw new Error(opened.error ?? "La API de Python no arrancó.");
        }
        session.current = opened;
        const prefs = await getPrefs(opened);
        if (alive) {
          setView((current) => viewFromPrefs(prefs, current));
        }
      })
      .catch((reason: unknown) => {
        if (alive) {
          setError(message(reason));
        }
      });
    return () => {
      alive = false;
    };
  }, [desktop, connect]);

  useEffect(() => {
    document.documentElement.dataset.theme = view.theme;
  }, [view.theme]);

  const remember = useCallback((key: ViewPrefKey, value: string) => {
    if (session.current === null) {
      return;
    }
    savePref(session.current, key, value).catch((reason: unknown) => setError(message(reason)));
  }, []);

  const chooseModule = useCallback(
    (module: ModuleId) => {
      setView((current) => ({ ...current, module }));
      remember("module", module);
    },
    [remember],
  );

  const cycleTheme = useCallback(() => {
    const theme = nextTheme(view.theme);
    setView((current) => ({ ...current, theme }));
    remember("theme", theme);
  }, [remember, view.theme]);

  return { ...view, error, chooseModule, cycleTheme };
}
