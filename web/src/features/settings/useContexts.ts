// Los pedidos de la pestana Contexto: usar otro contexto (rehace la foto), crear, renombrar,
// recargar y abrir la carpeta o contexto.md con la aplicacion del sistema. La lista y el
// aviso de la foto llegan por el canal de la configuracion (useSettings); aqui solo se
// pone sin esperar la lista que respondio cada pedido. Lo guardado es lo que lee Qt.
import { useCallback, useState } from "react";
import { contextsApi } from "../../api/client";
import { errorMessage } from "../../api/follow";
import type { ApiSession, ContextsData } from "../../api/types";

export interface ContextActions {
  /** Por que fallo el ultimo pedido; null si todo va bien. */
  error: string | null;
  /** "" deja al Agente sin contexto. */
  choose: (name: string) => void;
  create: () => void;
  rename: (name: string, typed: string) => void;
  reload: () => void;
  openFolder: () => void;
  openSnapshot: () => void;
}

export function useContexts(
  session: ApiSession | null,
  onContexts: (contexts: ContextsData) => void,
): ContextActions {
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    (request: (opened: ApiSession) => Promise<ContextsData>) => {
      if (session === null) {
        return;
      }
      setError(null);
      request(session)
        .then(onContexts)
        .catch((reason: unknown) => setError(errorMessage(reason)));
    },
    [session, onContexts],
  );

  const choose = useCallback(
    (name: string) => run((opened) => contextsApi.setActive(opened, name)),
    [run],
  );
  const create = useCallback(() => run((opened) => contextsApi.create(opened)), [run]);
  const rename = useCallback(
    (name: string, typed: string) => {
      const wanted = typed.trim();
      if (wanted !== "" && wanted !== name) {
        run((opened) => contextsApi.rename(opened, name, wanted));
      }
    },
    [run],
  );
  const reload = useCallback(() => run((opened) => contextsApi.reload(opened)), [run]);
  const openFolder = useCallback(() => run((opened) => contextsApi.openFolder(opened)), [run]);
  const openSnapshot = useCallback(() => run((opened) => contextsApi.openSnapshot(opened)), [run]);

  return { error, choose, create, rename, reload, openFolder, openSnapshot };
}
