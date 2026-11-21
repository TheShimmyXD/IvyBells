// Los menus de equipo de Ellos y Tu: se leen al abrir, cada vez que la escucha queda
// detenida y al desplegar un menu (Qt refresca los combos antes de iniciar); elegir lo
// recuerda la API al momento. Sin sesion (fuera de Tauri) muestra `seed`, si hay.
import { useCallback, useEffect, useState } from "react";
import { listeningApi } from "../../api/client";
import { errorMessage } from "../../api/follow";
import type { ApiSession, SourceId, SourceMenus } from "../../api/types";

export interface SourceMenusState {
  menus: SourceMenus | null;
  /** Por que fallo la ultima lectura o eleccion; null si todo va bien. */
  error: string | null;
  refresh: () => void;
  choose: (source: SourceId, name: string) => void;
}

export function useSourceMenus(
  session: ApiSession | null,
  idle: boolean,
  seed: SourceMenus | null = null,
): SourceMenusState {
  const [menus, setMenus] = useState<SourceMenus | null>(seed);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    (request: (opened: ApiSession) => Promise<SourceMenus>) => {
      if (session === null) {
        return;
      }
      request(session)
        .then((answer) => {
          setMenus(answer);
          setError(null);
        })
        .catch((reason: unknown) => setError(errorMessage(reason)));
    },
    [session],
  );

  const refresh = useCallback(() => run((opened) => listeningApi.sources(opened)), [run]);

  useEffect(() => {
    if (idle) {
      refresh();
    }
  }, [idle, refresh]);

  const choose = useCallback(
    (source: SourceId, name: string) =>
      run((opened) => listeningApi.chooseDevice(opened, source, name)),
    [run],
  );

  return { menus, error, refresh, choose };
}
