// Pestana Contexto (direccion 2d): a la izquierda los contextos (Sin contexto primero, "en
// uso" en el del Agente, + para uno nuevo); elegir uno lo pone en uso y rehace la foto,
// como el combo de Qt. A la derecha el contexto en uso: cabecera, el aviso de la foto, la
// barra con el peso de cada archivo en contexto.md y la lista de archivos.
import Icon from "../../shared/Icon";
import { thousands } from "../../shared/format";
import ContextHeader from "./ContextHeader";
import { contextRows, isReloading, noticeTone, tokensLabel, weightBar } from "./contextView";
import type { SettingsView } from "./settingsView";
import type { ContextActions } from "./useContexts";
import "./profile.css";
import "./context.css";

interface ContextTabProps {
  view: SettingsView;
  actions: ContextActions;
}

export default function ContextTab({ view, actions }: ContextTabProps) {
  const { contexts, contextNotice } = view;
  const rows = contextRows(contexts);
  const bar = weightBar(contexts.entries);
  const reloading = isReloading(contexts, contextNotice);
  return (
    <div className="profile">
      <section className="settings-panel profile-list" aria-label="Contextos">
        <header className="profile-list-head">
          <span className="settings-caption">Contextos</span>
          <button
            type="button"
            className="profile-icon"
            aria-label="Contexto nuevo"
            title="Contexto nuevo"
            onClick={actions.create}
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
                aria-current={row.active}
                onClick={() => actions.choose(row.name)}
              >
                <Icon name={row.name === "" ? "prohibit" : "folder-simple"} size={14} />
                <span className="profile-row-name">{row.label}</span>
                {row.active && row.name !== "" && <span className="profile-in-use">en uso</span>}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="settings-panel profile-editor" aria-label="Contexto en uso">
        {contexts.active === "" ? (
          <p className="muted context-empty">
            Sin contexto: el Agente responde solo con las reglas y el perfil. Elige un contexto o
            crea uno con +.
          </p>
        ) : (
          <>
            <ContextHeader
              key={contexts.active}
              name={contexts.active}
              folder={contexts.folder}
              reloading={reloading}
              actions={actions}
            />
            {actions.error !== null && (
              <p role="alert" className="settings-alert profile-error">
                {actions.error}
              </p>
            )}
            {contextNotice.text !== "" && (
              <p className="context-notice" data-tone={noticeTone(contextNotice)} role="status">
                {contextNotice.text}
              </p>
            )}
            <div className="context-weight">
              <span>Peso de cada archivo en contexto.md</span>
              <span className="context-total">~{thousands(bar.total)} tokens</span>
            </div>
            <div className="context-strip" aria-hidden="true">
              {bar.parts.map((part) => (
                <span
                  key={part.name}
                  className="context-segment"
                  data-tone={part.tone}
                  style={{ width: `${part.share}%` }}
                />
              ))}
            </div>
            {bar.parts.length === 0 ? (
              <p className="muted">
                La carpeta está vacía: abre la carpeta, copia ahí los archivos y pulsa Recargar.
              </p>
            ) : (
              <ul className="context-files" aria-label="Archivos del contexto">
                {bar.parts.map((part) => (
                  <li key={part.name} className="context-file">
                    <span className="context-dot" data-tone={part.tone} />
                    <Icon name={part.folder ? "folder-simple" : "file-text"} size={14} />
                    <span className="profile-row-name">{part.name}</span>
                    <span className="context-tokens">{tokensLabel(part.tokens)}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        <footer className="profile-foot context-foot">
          <Icon name="info" size={14} />
          <span>
            Se juntan en{" "}
            <button type="button" className="context-link" onClick={actions.openSnapshot}>
              contexto/contexto.md
            </button>{" "}
            y van en cada envío. Es una foto: tras cambiar un archivo, Recargar. Lee texto, PDF y
            Word.
          </span>
        </footer>
      </section>
    </div>
  );
}
