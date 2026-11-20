// Barra de arriba de En vivo: la capsula de estado con el modelo dentro y, a la derecha,
// Iniciar o Detener. Solo pinta y avisa clics.
import type { ListeningStateName, LiveModel } from "../../api/types";
import Icon from "../../shared/Icon";
import { runAction, stateTone } from "./liveText";

interface StatusBarProps {
  state: ListeningStateName;
  status: string;
  message: string;
  model: string;
  models: LiveModel[];
  onModel: (model: string) => void;
  onStart: () => void;
  onStop: () => void;
}

const RUN_LABELS = { start: "Iniciar", stop: "Detener", wait: "Deteniendo..." } as const;

export default function StatusBar(props: StatusBarProps) {
  const action = runAction(props.state);
  const idle = action === "start";
  const current = props.models.find((entry) => entry.key === props.model);
  return (
    <header className="live-top">
      <div className="live-capsule" data-tone={stateTone(props.state)}>
        <span className="live-dot" aria-hidden="true" />
        <span role="status" className="live-status">
          {props.status}
          {props.message && <span className="live-reason"> · {props.message}</span>}
        </span>
        <select
          className="live-model"
          aria-label="Modelo de transcripción"
          title={current?.help}
          value={props.model}
          disabled={!idle}
          onChange={(event) => props.onModel(event.target.value)}
        >
          {current === undefined && <option value={props.model}>{props.model || "-"}</option>}
          {props.models.map((entry) => (
            <option key={entry.key} value={entry.key} title={entry.help}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        className="live-run"
        data-action={action}
        disabled={action === "wait"}
        onClick={idle ? props.onStart : props.onStop}
      >
        <Icon name={idle ? "play" : "stop"} size={15} />
        {RUN_LABELS[action]}
      </button>
    </header>
  );
}
