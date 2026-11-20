// El esfuerzo como escala de seis pasos (dirección 2d): un punto por nivel unidos por una
// linea, el elegido mas grande y con su nombre en negrita. Es un grupo de radios: se elige
// con clic o con las flechas del teclado.
import type { ChatChoice } from "../../api/types";

interface EffortScaleProps {
  efforts: ChatChoice[];
  value: string;
  onChoose: (effort: string) => void;
}

export default function EffortScale({ efforts, value, onChoose }: EffortScaleProps) {
  const chosen = efforts.findIndex((entry) => entry.key === value);
  return (
    <div className="settings-scale" role="radiogroup" aria-label="Esfuerzo">
      <div className="settings-scale-steps">
        {efforts.map((entry, index) => (
          <label
            key={entry.key}
            className="settings-step"
            data-reached={chosen >= 0 && index <= chosen}
            title={entry.help || undefined}
          >
            <input
              type="radio"
              name="effort"
              className="visually-hidden"
              checked={entry.key === value}
              onChange={() => onChoose(entry.key)}
            />
            <span className="settings-step-dot" aria-hidden="true" />
            <span className="settings-step-label">{entry.label}</span>
          </label>
        ))}
      </div>
      <div className="settings-scale-ends" aria-hidden="true">
        <span>más rápido</span>
        <span>razona más</span>
      </div>
    </div>
  );
}
