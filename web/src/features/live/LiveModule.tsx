// La vista En vivo, direccion 2b: estado arriba, la conversacion con sus canales a
// la izquierda, el panel del Agente a la derecha y el pie con latencia, ruta y Guardar.
import type { LiveListening } from "./useLiveListening";
import AgentPanel, { type AgentTab } from "./AgentPanel";
import ChannelHeader from "./ChannelHeader";
import Conversation from "./Conversation";
import LiveFooter from "./LiveFooter";
import StatusBar from "./StatusBar";
import { conversation } from "./conversation";
import "./live.css";

interface LiveModuleProps {
  live: LiveListening;
  agentTab: AgentTab;
  onAgentTab: (tab: AgentTab) => void;
  /** Pide al usuario donde guardar la copia (recibe el .md actual); sin el, Guardar queda apagado. */
  choosePath?: (lastPath: string | null) => Promise<string | null>;
  /** Que decir mientras no hay vista (sin API); por defecto, que se esta conectando. */
  waiting?: string;
}

export default function LiveModule(props: LiveModuleProps) {
  const { live, agentTab, onAgentTab, choosePath } = props;
  const { view } = live;
  const onSave =
    choosePath === undefined
      ? undefined
      : () => {
          void choosePath(view?.path ?? null).then((path) => path !== null && live.save(path));
        };
  return (
    <section className="live" aria-labelledby="live-title">
      <h1 id="live-title" className="visually-hidden">
        En vivo
      </h1>
      {view === null ? (
        <p className="live-waiting">
          {live.error ?? props.waiting ?? "Conectando con la escucha..."}
        </p>
      ) : (
        <>
          <StatusBar
            state={view.state}
            status={view.status}
            message={view.message}
            model={live.model}
            models={view.models}
            onModel={live.chooseModel}
            onStart={live.start}
            onStop={live.stop}
          />
          {(live.error ?? live.notice) !== null && (
            <p className="live-alert" role="alert" data-tone={live.error ? "error" : "warning"}>
              {live.error ?? live.notice}
            </p>
          )}
          <div className="live-body">
            <section className="live-card" aria-label="Transcripción">
              <ChannelHeader
                devices={view.devices}
                closed={view.closed}
                onToggle={live.toggleSource}
              />
              <Conversation bubbles={conversation(view)} closed={view.closed} />
            </section>
            <AgentPanel tab={agentTab} onTab={onAgentTab} />
          </div>
          <LiveFooter
            latency={view.latency}
            path={view.path}
            savedCopy={view.savedCopy}
            onSave={onSave}
          />
        </>
      )}
    </section>
  );
}
