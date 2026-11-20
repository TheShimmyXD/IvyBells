// El modulo Configuracion de la web (FW.9, direccion 2d): titulo, pestanas Claude | Perfil
// del agente | Contexto y el aviso de que cada cambio se guarda al momento. Perfil y
// Contexto llegan en los pasos siguientes; hoy se editan en Qt.
import { useState } from "react";
import Icon from "../../shared/Icon";
import type { IconName } from "../../shared/phosphor";
import ClaudeTab from "./ClaudeTab";
import type { Settings } from "./useSettings";
import "./settings.css";

type SettingsTab = "claude" | "profile" | "context";

const TABS: readonly { id: SettingsTab; label: string; icon: IconName }[] = [
  { id: "claude", label: "Claude", icon: "sparkle" },
  { id: "profile", label: "Perfil del agente", icon: "article" },
  { id: "context", label: "Contexto", icon: "folder-simple" },
];

interface SettingsModuleProps {
  settings: Settings;
  /** El aviso cuando no hay API (fuera de Tauri y sin ?demo=1). */
  waiting?: string;
}

export default function SettingsModule({ settings, waiting }: SettingsModuleProps) {
  const [tab, setTab] = useState<SettingsTab>("claude");
  const { view, error } = settings;
  return (
    <div className="settings">
      <header className="settings-head">
        <h1>Configuración</h1>
        <div className="settings-tabs" role="tablist" aria-label="Configuración">
          {TABS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              role="tab"
              aria-selected={entry.id === tab}
              className="settings-tab"
              onClick={() => setTab(entry.id)}
            >
              <Icon name={entry.icon} size={14} />
              {entry.label}
            </button>
          ))}
        </div>
        <span className="settings-saved">
          <Icon name="check" size={13} />
          Cada cambio se guarda al momento
        </span>
      </header>
      {error !== null && (
        <p role="alert" className="settings-alert">
          {error}
        </p>
      )}
      {view === null ? (
        <p className="muted">{waiting ?? "Cargando la configuración..."}</p>
      ) : tab === "claude" ? (
        <ClaudeTab view={view} settings={settings} />
      ) : (
        <p className="settings-later muted">
          Esta pestaña llega a la web en el paso siguiente; hoy se edita en la ventana de Qt.
        </p>
      )}
    </div>
  );
}
