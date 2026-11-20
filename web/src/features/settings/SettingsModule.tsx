// El modulo Configuracion de la web (FW.9, direccion 2d): titulo, pestanas Claude | Perfil
// del agente | Contexto y el aviso de que cada cambio se guarda al momento.
import { useState } from "react";
import Icon from "../../shared/Icon";
import type { IconName } from "../../shared/phosphor";
import ClaudeTab from "./ClaudeTab";
import ContextTab from "./ContextTab";
import type { DemoSettingsTab } from "./demo";
import ProfileTab from "./ProfileTab";
import type { ContextActions } from "./useContexts";
import type { ProfileEditor } from "./useProfiles";
import type { Settings } from "./useSettings";
import "./settings.css";

type SettingsTab = DemoSettingsTab;

const TABS: readonly { id: SettingsTab; label: string; icon: IconName }[] = [
  { id: "claude", label: "Claude", icon: "sparkle" },
  { id: "profile", label: "Perfil del agente", icon: "article" },
  { id: "context", label: "Contexto", icon: "folder-simple" },
];

interface SettingsModuleProps {
  settings: Settings;
  profiles: ProfileEditor;
  contexts: ContextActions;
  /** La pestana con que abre (las capturas piden otra con &tab=). */
  firstTab?: SettingsTab;
  /** El aviso cuando no hay API (fuera de Tauri y sin ?demo=1). */
  waiting?: string;
}

export default function SettingsModule({
  settings,
  profiles,
  contexts,
  firstTab = "claude",
  waiting,
}: SettingsModuleProps) {
  const [tab, setTab] = useState<SettingsTab>(firstTab);
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
      ) : tab === "profile" ? (
        <ProfileTab view={view} editor={profiles} />
      ) : (
        <ContextTab view={view} actions={contexts} />
      )}
    </div>
  );
}
