// La ventana: la barra de modulos y el area de trabajo del modulo elegido. En vivo ya esta
// en la web (FW.7); Configuracion llega en FW.9 y hoy se usa en la ventana de Qt.
import { useMemo, useState } from "react";
import { runsInDesktop } from "./api/session";
import type { ApiSession } from "./api/types";
import type { AgentTab } from "./features/live/AgentPanel";
import LiveModule from "./features/live/LiveModule";
import { chooseSavePath } from "./features/live/savePath";
import { demoAgent, demoView } from "./features/live/demo";
import { useAgent } from "./features/live/useAgent";
import { useLiveListening } from "./features/live/useLiveListening";
import { MODULES, wantsDemo } from "./shell/modules";
import Sidebar from "./shell/Sidebar";
import { useViewPrefs } from "./shell/useViewPrefs";
import "./App.css";

interface AppProps {
  desktop?: boolean;
  connect?: () => Promise<ApiSession>;
}

const NO_API_MESSAGE = "Fuera de la ventana no hay escucha: abre con ?demo=1 para ver un ejemplo.";

export default function App({ desktop = runsInDesktop(), connect }: AppProps) {
  const view = useViewPrefs(desktop, connect);
  const current = MODULES.find((entry) => entry.id === view.module) ?? MODULES[0];
  const seed = useMemo(
    () => (!desktop && wantsDemo(window.location.search) ? demoView() : null),
    [desktop],
  );
  const recordedModel = typeof view.prefs.live_model === "string" ? view.prefs.live_model : null;
  const live = useLiveListening(view.session, recordedModel, seed);
  const agentSeed = useMemo(
    () => (seed === null ? null : demoAgent(window.location.search)),
    [seed],
  );
  const agent = useAgent(view.session, agentSeed);
  const [chosenTab, setChosenTab] = useState<AgentTab | null>(null);
  const agentTab = chosenTab ?? (view.prefs.agent_panel === "chat" ? "chat" : "agent");
  const chooseTab = (tab: AgentTab) => {
    setChosenTab(tab);
    view.remember("agent_panel", tab);
  };
  const waiting = !desktop && seed === null ? NO_API_MESSAGE : undefined;
  return (
    <div className="shell">
      <Sidebar
        module={view.module}
        theme={view.theme}
        onChoose={view.chooseModule}
        onCycleTheme={view.cycleTheme}
      />
      <main className="workspace">
        {view.error !== null && (
          <p role="alert" className="error">
            {view.error}
          </p>
        )}
        {current.id === "live" ? (
          <LiveModule
            live={live}
            agent={agent}
            agentTab={agentTab}
            onAgentTab={chooseTab}
            choosePath={desktop ? chooseSavePath : undefined}
            waiting={waiting}
          />
        ) : (
          <>
            <h1>{current.label}</h1>
            <p className="muted">{current.tip}</p>
            <p className="muted">
              Este módulo llega a la web más adelante; hoy se usa en la ventana de Qt.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
