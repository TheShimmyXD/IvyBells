// Panel del Agente: pestanas Agente | Chat, el interruptor Anticipado, como va el envio
// con Cancelar y la respuesta grande. Sin respuestas todavia, las teclas para marcar.
import type { AgentStateName } from "../../api/types";
import Icon from "../../shared/Icon";
import AgentAnswer from "./AgentAnswer";
import { answerBoard, canCancel, type AgentView } from "./agentView";

export type AgentTab = "agent" | "chat";

interface AgentPanelProps {
  tab: AgentTab;
  onTab: (tab: AgentTab) => void;
  /** El Agente de la API; null mientras se conecta. */
  agent: AgentView | null;
  /** Por que fallo el ultimo pedido al Agente. */
  error: string | null;
  onCancel: () => void;
}

const TONES: Record<AgentStateName, string> = {
  idle: "idle",
  start_marked: "ok",
  sending: "busy",
  answered: "ok",
  error: "error",
};

const KEYS = [
  ["Clic izq.", "inicio"],
  ["Clic der.", "final y enviar"],
  ["Esc", "cancelar"],
] as const;

export default function AgentPanel({ tab, onTab, agent, error, onCancel }: AgentPanelProps) {
  const board = agent === null ? null : answerBoard(agent);
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
          <div className="live-agent-hint" data-tone={agent === null ? "idle" : TONES[agent.state]}>
            <span className="live-dot" aria-hidden="true" />
            <span aria-live="polite">{agent?.status ?? "Conectando con el Agente..."}</span>
            {agent !== null && canCancel(agent.state) && (
              <button type="button" className="live-cancel" onClick={onCancel}>
                Cancelar
              </button>
            )}
          </div>
          {error !== null && (
            <p className="live-agent-error" role="alert">
              {error}
            </p>
          )}
          {board === null || board.card === null ? (
            <>
              <p className="live-agent-lead">
                Marca lo que dijo el cliente y la respuesta sale aquí, grande, para leerla en voz
                alta.
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
            </>
          ) : (
            <AgentAnswer {...board} />
          )}
        </div>
      ) : (
        <div className="live-agent-body" role="tabpanel" aria-label="Chat">
          <p className="live-agent-lead">Pregunta sobre lo dicho: el chat llega con el Agente.</p>
        </div>
      )}
    </aside>
  );
}
