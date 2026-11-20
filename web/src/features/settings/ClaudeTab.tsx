// Pestana Claude de la Configuracion (direccion 2d): la cuenta arriba; a la izquierda el
// modelo en tarjetas con su ayuda y el esfuerzo en escala; a la derecha lo que pasa si
// Claude no responde (respaldo y tiempo maximo).
import Icon from "../../shared/Icon";
import AccountCard from "./AccountCard";
import EffortScale from "./EffortScale";
import { effortHelp, fallbackLabel, timeoutLabel } from "./settingsView";
import type { Settings } from "./useSettings";
import type { SettingsView } from "./settingsView";

interface ClaudeTabProps {
  view: SettingsView;
  settings: Settings;
}

export default function ClaudeTab({ view, settings }: ClaudeTabProps) {
  const { config, choices } = view;
  return (
    <div className="settings-claude">
      <AccountCard
        key={config.account}
        account={config.account}
        status={view.account}
        onAccount={settings.setAccount}
        onCheck={settings.check}
      />
      <div className="settings-columns">
        <section className="settings-panel" aria-label="Modelo y esfuerzo">
          <h2 className="settings-title">
            Modelo <span className="settings-help">con qué responde el Agente</span>
          </h2>
          <div className="settings-models" role="radiogroup" aria-label="Modelo">
            {choices.models.map((entry) => (
              <label key={entry.key} className="settings-model">
                <input
                  type="radio"
                  name="model"
                  className="visually-hidden"
                  checked={entry.key === config.model}
                  onChange={() => settings.setModel(entry.key)}
                />
                <span className="settings-model-name">
                  {entry.label}
                  {entry.key === config.model && <Icon name="check-circle" size={16} />}
                </span>
                <span className="settings-model-help">{entry.help}</span>
              </label>
            ))}
          </div>
          <h2 className="settings-title">
            Esfuerzo <span className="settings-help">{effortHelp(choices, config.effort)}</span>
          </h2>
          <EffortScale
            efforts={choices.efforts}
            value={config.effort}
            onChoose={settings.setEffort}
          />
        </section>
        <section className="settings-panel settings-side" aria-label="Si no responde">
          <h2 className="settings-title">Si no responde</h2>
          <span className="settings-caption">Modelo de respaldo</span>
          <div className="settings-fallbacks" role="radiogroup" aria-label="Modelo de respaldo">
            {choices.fallbacks.map((key) => (
              <label key={key} className="settings-fallback">
                <input
                  type="radio"
                  name="fallback"
                  checked={key === config.fallback_model}
                  onChange={() => settings.setFallback(key)}
                />
                {fallbackLabel(key)}
              </label>
            ))}
          </div>
          <span className="settings-caption">Tiempo máximo de espera</span>
          <div className="settings-timeouts" role="radiogroup" aria-label="Tiempo máximo de espera">
            {choices.timeouts_s.map((seconds) => (
              <button
                key={seconds}
                type="button"
                role="radio"
                aria-checked={seconds === config.timeout_s}
                className="settings-timeout"
                onClick={() => settings.setTimeout(seconds)}
              >
                {timeoutLabel(seconds)}
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
