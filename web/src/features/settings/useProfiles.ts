// El editor de perfiles del Agente: abre el texto del perfil elegido, lo guarda solo tras
// SAVE_DELAY_MS sin escribir (o al salir del campo) y manda crear, copiar, renombrar, borrar
// y "Usar en el Agente". La API guarda en resources/agent/perfiles/ y app_settings.json.
import { useCallback, useEffect, useRef, useState } from "react";
import { profilesApi } from "../../api/client";
import { errorMessage } from "../../api/follow";
import type { ApiSession, ProfileChange, ProfilesData, ProfileText } from "../../api/types";
import { pickProfile, renamedTo, SAVE_DELAY_MS, type SaveState } from "./profileView";

/** Sin API (capturas con ?demo=1): el perfil abierto y el texto de cada uno. */
export interface ProfileSeed {
  selected: string | null;
  texts: Record<string, string>;
}

export interface ProfileEditor {
  /** El perfil abierto ("" si no hay ninguno). */
  current: string;
  text: string;
  editable: boolean;
  loading: boolean;
  saveState: SaveState;
  error: string | null;
  select: (name: string) => void;
  edit: (text: string) => void;
  /** Guarda ya lo que espera su turno (al salir del campo). */
  flush: () => void;
  use: () => void;
  create: () => void;
  duplicate: () => void;
  rename: (typed: string) => void;
  remove: () => void;
}

interface Pending {
  name: string;
  text: string;
  timer: number;
}

export function useProfiles(
  session: ApiSession | null,
  profiles: ProfilesData | null,
  onProfiles: (profiles: ProfilesData) => void,
  seed: ProfileSeed | null = null,
): ProfileEditor {
  const [wanted, setWanted] = useState<string | null>(seed?.selected ?? null);
  const [opened, setOpened] = useState<ProfileText | null>(null);
  const [draft, setDraft] = useState<{ name: string; text: string } | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<Pending | null>(null);
  const current = profiles === null ? "" : pickProfile(profiles, wanted);

  useEffect(() => {
    if (session === null || current === "") {
      return;
    }
    let live = true;
    profilesApi
      .read(session, current)
      .then((profile) => {
        if (live) {
          setOpened(profile);
          setSaveState("saved");
        }
      })
      .catch((reason: unknown) => live && setError(errorMessage(reason)));
    return () => {
      live = false;
    };
  }, [session, current]);

  const shown: ProfileText | null =
    session === null && seed !== null && profiles !== null && current !== ""
      ? {
          name: current,
          text: seed.texts[current] ?? "",
          editable: profiles.editable.includes(current),
        }
      : opened !== null && opened.name === current
        ? opened
        : null;

  const save = useCallback(
    (name: string, text: string): Promise<void> => {
      if (session === null) {
        setSaveState("saved");
        return Promise.resolve();
      }
      setSaveState("saving");
      return profilesApi
        .save(session, name, text)
        .then((change) => {
          onProfiles(change);
          setOpened((last) => (last !== null && last.name === name ? { ...last, text } : last));
          if (pending.current === null) {
            setSaveState("saved");
          }
        })
        .catch((reason: unknown) => {
          setSaveState("error");
          setError(errorMessage(reason));
        });
    },
    [session, onProfiles],
  );

  const flushNow = useCallback((): Promise<void> => {
    const waiting = pending.current;
    if (waiting === null) {
      return Promise.resolve();
    }
    window.clearTimeout(waiting.timer);
    pending.current = null;
    return save(waiting.name, waiting.text);
  }, [save]);

  // Al cerrar la ventana o el modulo no se pierde lo escrito en el ultimo instante.
  useEffect(() => () => void flushNow(), [flushNow]);

  const editable = shown?.editable ?? false;

  const edit = useCallback(
    (text: string) => {
      setDraft({ name: current, text });
      if (!editable) {
        return;
      }
      if (pending.current !== null) {
        window.clearTimeout(pending.current.timer);
      }
      setSaveState("pending");
      const name = current;
      const timer = window.setTimeout(() => {
        pending.current = null;
        void save(name, text);
      }, SAVE_DELAY_MS);
      pending.current = { name, text, timer };
    },
    [current, editable, save],
  );

  /** Guarda lo pendiente y despues manda el pedido; then recibe lo que respondio. */
  const run = useCallback(
    (
      request: (opened: ApiSession) => Promise<ProfilesData | ProfileChange>,
      then: (data: ProfilesData | ProfileChange) => void = () => undefined,
    ) => {
      if (session === null) {
        return;
      }
      setError(null);
      void flushNow()
        .then(() => request(session))
        .then((data) => {
          onProfiles(data);
          then(data);
        })
        .catch((reason: unknown) => setError(errorMessage(reason)));
    },
    [session, flushNow, onProfiles],
  );

  const openReturned = (data: ProfilesData | ProfileChange) => {
    if ("name" in data) {
      setWanted(data.name);
    }
  };

  return {
    current,
    text: draft !== null && draft.name === current ? draft.text : (shown?.text ?? ""),
    editable,
    loading: current !== "" && shown === null,
    saveState,
    error,
    select: (name) => {
      setError(null);
      void flushNow().then(() => setWanted(name));
    },
    edit,
    flush: () => void flushNow(),
    use: () => run((opened) => profilesApi.setActive(opened, current)),
    create: () => run((opened) => profilesApi.create(opened), openReturned),
    duplicate: () => run((opened) => profilesApi.duplicate(opened, current), openReturned),
    rename: (typed) => {
      const name = renamedTo(typed, current);
      if (name !== null) {
        run((opened) => profilesApi.rename(opened, current, name), openReturned);
      }
    },
    remove: () =>
      run(
        (opened) => profilesApi.remove(opened, current),
        () => setWanted(null),
      ),
  };
}
