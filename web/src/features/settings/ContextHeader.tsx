// Cabecera del contexto en uso (direccion 2d): su nombre, que se renombra en el sitio, la
// carpeta debajo, "Abrir carpeta" y "Recargar" (rehace contexto.md tras cambiar archivos).
// Se monta con key={nombre}: cambiar de contexto la reinicia.
import { useState } from "react";
import Icon from "../../shared/Icon";
import { shortFolder } from "./contextView";
import type { ContextActions } from "./useContexts";

interface ContextHeaderProps {
  name: string;
  folder: string | null;
  reloading: boolean;
  actions: ContextActions;
}

export default function ContextHeader({ name, folder, reloading, actions }: ContextHeaderProps) {
  const [typed, setTyped] = useState<string | null>(null);
  const finishRename = () => {
    if (typed !== null) {
      actions.rename(name, typed);
    }
    setTyped(null);
  };
  return (
    <header className="profile-head context-head">
      <div className="context-title">
        {typed === null ? (
          <h2 className="profile-name">{name}</h2>
        ) : (
          <input
            className="settings-account-input profile-rename"
            aria-label="Nombre nuevo del contexto"
            value={typed}
            autoFocus
            onChange={(event) => setTyped(event.target.value)}
            onBlur={finishRename}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                finishRename();
              } else if (event.key === "Escape") {
                setTyped(null);
              }
            }}
          />
        )}
        <span className="context-folder" title={folder ?? undefined}>
          {shortFolder(folder)}
        </span>
      </div>
      <button
        type="button"
        className="profile-icon"
        aria-label="Renombrar"
        title="Renombrar"
        onClick={() => setTyped(name)}
      >
        <Icon name="pencil-simple" size={15} />
      </button>
      <button type="button" className="settings-button" onClick={actions.openFolder}>
        <Icon name="folder-open" size={14} />
        Abrir carpeta
      </button>
      <button
        type="button"
        className="settings-button context-reload"
        disabled={reloading}
        onClick={actions.reload}
      >
        <Icon name={reloading ? "circle-notch" : "arrows-clockwise"} size={14} />
        {reloading ? "Recargando..." : "Recargar"}
      </button>
    </header>
  );
}
