// La ventana: la barra de modulos y el area de trabajo del modulo elegido. En vivo con el
// Agente y el chat en su panel (FW.7, FW.8) y Configuracion (FW.9).
import { useMemo, useState } from "react";
import { runsInDesktop } from "./api/session";
import type { ApiSession } from "./api/types";
import ChatPanel from "./features/chat/ChatPanel";
import { demoChat, demoChatTab } from "./features/chat/demo";
import { useChat } from "./features/chat/useChat";
import type { AgentTab } from "./features/live/AgentPanel";
import LiveModule from "./features/live/LiveModule";
import { chooseSavePath } from "./features/live/savePath";
import { demoAgent, demoContextOpen, demoView } from "./features/live/demo";
import { useAgent } from "./features/live/useAgent";
import { useLiveListening } from "./features/live/useLiveListening";
import { demoSettings } from "./features/settings/demo";
import SettingsModule from "./features/settings/SettingsModule";
import { useSettings } from "./features/settings/useSettings";
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
  const chatSeed = useMemo(() => (seed === null ? null : demoChat(window.location.search)), [seed]);
  const chat = useChat(view.session, chatSeed);
  const settingsSeed = useMemo(
    () => (seed === null ? null : demoSettings(window.location.search)),
    [seed],
  );
  const settings = useSettings(view.session, settingsSeed);
  const [chosenTab, setChosenTab] = useState<AgentTab | null>(() =>
    seed !== null && demoChatTab(window.location.search) ? "chat" : null,
  );
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
            contextOpen={seed !== null && demoContextOpen(window.location.search)}
            chatPanel={<ChatPanel chat={chat} />}
          />
        ) : (
          <SettingsModule settings={settings} waiting={waiting} />
        )}
      </main>
    </div>
  );
}
