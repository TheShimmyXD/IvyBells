// Pestana Perfil del agente (direccion 2d): a la izquierda la lista de perfiles (candado en
// los de solo lectura, "en uso" en el del Agente, + para uno nuevo); a la derecha el perfil
// abierto con su cabecera y el texto, que se guarda solo mientras se escribe.
import Icon from "../../shared/Icon";
import ProfileHeader from "./ProfileHeader";
import { profileRows } from "./profileView";
import type { SettingsView } from "./settingsView";
import type { ProfileEditor } from "./useProfiles";
import "./profile.css";

interface ProfileTabProps {
  view: SettingsView;
  editor: ProfileEditor;
}

export default function ProfileTab({ view, editor }: ProfileTabProps) {
  const rows = profileRows(view.profiles);
  return (
    <div className="profile">
      <section className="settings-panel profile-list" aria-label="Perfiles">
        <header className="profile-list-head">
          <span className="settings-caption">Perfiles</span>
          <button
            type="button"
            className="profile-icon"
            aria-label="Perfil nuevo"
            title="Perfil nuevo"
            onClick={editor.create}
          >
            <Icon name="plus" size={15} />
          </button>
        </header>
        <ul className="profile-rows">
          {rows.map((row) => (
            <li key={row.name}>
              <button
                type="button"
                className="profile-row"
                aria-current={row.name === editor.current}
                onClick={() => editor.select(row.name)}
              >
                <span className="profile-row-name">{row.name}</span>
                {row.locked && (
                  <span title="Solo lectura" className="profile-lock">
                    <Icon name="lock-simple" size={13} />
                  </span>
                )}
                {row.active && <span className="profile-in-use">en uso</span>}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="settings-panel profile-editor" aria-label="Perfil abierto">
        {editor.current === "" ? (
          <p className="muted">No hay perfiles: crea uno con +.</p>
        ) : (
          <>
            <ProfileHeader
              key={editor.current}
              editor={editor}
              active={editor.current === view.profiles.active}
            />
            {editor.error !== null && (
              <p role="alert" className="settings-alert profile-error">
                {editor.error}
              </p>
            )}
            <textarea
              className="profile-text"
              aria-label="Texto del perfil"
              value={editor.loading ? "" : editor.text}
              placeholder={editor.loading ? "Abriendo el perfil..." : "Escribe el rol del Agente."}
              readOnly={!editor.editable || editor.loading}
              spellCheck={false}
              onChange={(event) => editor.edit(event.target.value)}
              onBlur={editor.flush}
            />
            <footer className="profile-foot">
              <Icon name="shield-check" size={14} />
              {editor.editable
                ? "Rol, tono y datos de la empresa. Las reglas de seguridad las pone IvyBells siempre, antes de este texto."
                : "Este perfil es de solo lectura: cópialo para tener uno tuyo que se pueda editar."}
            </footer>
          </>
        )}
      </section>
    </div>
  );
}
