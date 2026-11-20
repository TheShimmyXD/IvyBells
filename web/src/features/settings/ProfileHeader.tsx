// Cabecera del perfil abierto (direccion 2d): su nombre, que se renombra en el sitio, las
// acciones en iconos (renombrar, copiar, borrar con confirmacion), "Usar en el Agente" y si
// el texto ya quedo guardado. Se monta con key={nombre}: cambiar de perfil la reinicia.
import { useState } from "react";
import Icon from "../../shared/Icon";
import { saveBadge } from "./profileView";
import type { ProfileEditor } from "./useProfiles";

interface ProfileHeaderProps {
  editor: ProfileEditor;
  active: boolean;
}

export default function ProfileHeader({ editor, active }: ProfileHeaderProps) {
  const [typed, setTyped] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const badge = saveBadge(editor.saveState, editor.editable);
  const finishRename = () => {
    if (typed !== null) {
      editor.rename(typed);
    }
    setTyped(null);
  };
  return (
    <>
      <header className="profile-head">
        {typed === null ? (
          <h2 className="profile-name">{editor.current}</h2>
        ) : (
          <input
            className="settings-account-input profile-rename"
            aria-label="Nombre nuevo del perfil"
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
        <div className="profile-actions">
          <button
            type="button"
            className="profile-icon"
            aria-label="Renombrar"
            title="Renombrar"
            disabled={!editor.editable}
            onClick={() => setTyped(editor.current)}
          >
            <Icon name="pencil-simple" size={15} />
          </button>
          <button
            type="button"
            className="profile-icon"
            aria-label="Copiar"
            title="Copiar"
            onClick={editor.duplicate}
          >
            <Icon name="copy" size={15} />
          </button>
          <button
            type="button"
            className="profile-icon"
            aria-label="Borrar"
            title="Borrar"
            disabled={!editor.editable}
            onClick={() => setConfirming(true)}
          >
            <Icon name="trash" size={15} />
          </button>
        </div>
        <button
          type="button"
          className="settings-button profile-use"
          disabled={active}
          onClick={editor.use}
        >
          {active ? "En uso en el Agente" : "Usar en el Agente"}
        </button>
        <span className="settings-badge" data-tone={badge.tone} role="status">
          {!editor.editable && <Icon name="lock-simple" size={13} />}
          {badge.text}
        </span>
      </header>
      {confirming && (
        <p className="profile-confirm" role="alert">
          ¿Borrar el perfil «{editor.current}»? No se puede deshacer.
          <button
            type="button"
            className="settings-button profile-danger"
            onClick={() => {
              setConfirming(false);
              editor.remove();
            }}
          >
            Borrar
          </button>
          <button type="button" className="settings-button" onClick={() => setConfirming(false)}>
            Cancelar
          </button>
        </p>
      )}
    </>
  );
}
