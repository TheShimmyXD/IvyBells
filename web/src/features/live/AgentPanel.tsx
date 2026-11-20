// Panel del Agente en reposo (FW.7): pestanas Agente | Chat, el interruptor Anticipado y
// las teclas para marcar a la vista. Marcar, enviar y el chat llegan en FW.8.
import Icon from "../../shared/Icon";

export type AgentTab = "agent" | "chat";

interface AgentPanelProps {
  tab: AgentTab;
  onTab: (tab: AgentTab) => void;
}

const KEYS = [
  ["Clic izq.", "inicio"],
  ["Clic der.", "final y enviar"],
  ["Esc", "cancelar"],
] as const;

export default function AgentPanel({ tab, onTab }: AgentPanelProps) {
  return (
    <aside className="live-agent" aria-label="Agente">
      <div className="live-agent-head" role="tablist" aria-label="Panel del Agente">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "agent"}
          className="live-tab"
          onClick={() => onTab("agent")}
        >
          <Icon name="robot" size={15} />
          Agente
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "chat"}
          className="live-tab"
          onClick={() => onTab("chat")}
        >
          <Icon name="chat-circle" size={15} />
          Chat
        </button>
        <span className="live-anticipated" title="Llega con el Agente (FW.8)">
          <Icon name="lightning" size={14} />
          Anticipado
          <button
            type="button"
            role="switch"
            className="live-switch"
            aria-checked={false}
            aria-label="Anticipado"
            disabled
          />
        </span>
      </div>
      {tab === "agent" ? (
        <div className="live-agent-body" role="tabpanel" aria-label="Agente">
          <p className="live-agent-hint">
            <span className="live-dot" aria-hidden="true" />
            Clic izquierdo marca el inicio
          </p>
          <p className="live-agent-lead">
            Marca lo que dijo el cliente y la respuesta sale aquí, grande, para leerla en voz alta.
          </p>
          <dl className="live-keys">
            {KEYS.map(([key, action]) => (
              <div key={key}>
                <dt>
                  <kbd>{key}</kbd>
                </dt>
                <dd>{action}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : (
        <div className="live-agent-body" role="tabpanel" aria-label="Chat">
          <p className="live-agent-lead">Pregunta sobre lo dicho: el chat llega con el Agente.</p>
        </div>
      )}
    </aside>
  );
}
