// La vista En vivo, direccion 2b: estado arriba, la conversacion con sus canales a
// la izquierda, el panel del Agente a la derecha y el pie con latencia, ruta y Guardar.
import { useEffect, useMemo, type ReactNode } from "react";
import type { Agent } from "./useAgent";
import type { LiveListening } from "./useLiveListening";
import type { SourceMenusState } from "./useSourceMenus";
import type { SourceId } from "../../api/types";
import AgentPanel, { type AgentTab } from "./AgentPanel";
import ChannelHeader from "./ChannelHeader";
import Conversation from "./Conversation";
import LiveFooter from "./LiveFooter";
import StatusBar from "./StatusBar";
import { canCancel, phraseMarks } from "./agentView";
import { conversation } from "./conversation";
import { runAction } from "./liveText";
import "./live.css";
import "./agent.css";
import "./contextBar.css";

interface LiveModuleProps {
  live: LiveListening;
  agent: Agent;
  agentTab: AgentTab;
  onAgentTab: (tab: AgentTab) => void;
  /** Pide al usuario donde guardar la copia (recibe el .md actual); sin el, Guardar queda apagado. */
  choosePath?: (lastPath: string | null) => Promise<string | null>;
  /** Que decir mientras no hay vista (sin API); por defecto, que se esta conectando. */
  waiting?: string;
  /** Demo: el desglose de la barra de contexto abierto. */
  contextOpen?: boolean;
  /** La pestana Chat del panel del Agente (feature chat, la compone App). */
  chatPanel?: ReactNode;
  /** Los menus de equipo de la cabecera; sin ellos, el equipo es solo texto. */
  sources?: SourceMenusState;
  /** Demo: el menu de equipo de este canal abierto para la captura. */
  openMenu?: SourceId | null;
}

export default function LiveModule(props: LiveModuleProps) {
  const { live, agent, agentTab, onAgentTab, choosePath, sources } = props;
  const { view } = live;
  const agentView = agent.view;
  const cancellable = agentView !== null && canCancel(agentView.state);
  const { cancel } = agent;
  useEffect(() => {
    if (!cancellable) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        cancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cancellable, cancel]);
  const marks = useMemo(
    () => (agentView === null ? undefined : phraseMarks(agentView)),
    [agentView],
  );
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
          {(live.error ?? sources?.error ?? live.notice) != null && (
            <p
              className="live-alert"
              role="alert"
              data-tone={(live.error ?? sources?.error) ? "error" : "warning"}
            >
              {live.error ?? sources?.error ?? live.notice}
            </p>
          )}
          <div className="live-body">
            <section className="live-card" aria-label="Transcripción">
              <ChannelHeader
                devices={view.devices}
                closed={view.closed}
                onToggle={live.toggleSource}
                menus={sources?.menus}
                editable={runAction(view.state) === "start"}
                onChooseDevice={sources?.choose}
                onOpenMenu={sources?.refresh}
                openMenu={props.openMenu}
              />
              <Conversation
                bubbles={conversation(view)}
                closed={view.closed}
                agent={
                  agentView === null || marks === undefined
                    ? undefined
                    : { speaker: agentView.speaker, marks, onMark: agent.mark }
                }
              />
            </section>
            <AgentPanel
              tab={agentTab}
              onTab={onAgentTab}
              agent={agentView}
              error={agent.error}
              onCancel={cancel}
              onMode={agent.setMode}
              contextOpen={props.contextOpen}
              chatPanel={props.chatPanel}
            />
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
