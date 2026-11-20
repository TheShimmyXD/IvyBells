// La ventana: la barra de modulos y el area de trabajo del modulo elegido (vacios hasta
// FW.7 a FW.9; la ventana de Qt sigue siendo la que se usa).
import type { ApiSession } from "./api/types";
import { MODULES } from "./shell/modules";
import Sidebar from "./shell/Sidebar";
import { useViewPrefs } from "./shell/useViewPrefs";
import "./App.css";

interface AppProps {
  desktop?: boolean;
  connect?: () => Promise<ApiSession>;
}

export default function App({ desktop, connect }: AppProps) {
  const view = useViewPrefs(desktop, connect);
  const current = MODULES.find((entry) => entry.id === view.module) ?? MODULES[0];
  return (
    <div className="shell">
      <Sidebar
        module={view.module}
        theme={view.theme}
        onChoose={view.chooseModule}
        onCycleTheme={view.cycleTheme}
      />
      <main className="workspace">
        <h1>{current.label}</h1>
        <p className="muted">{current.tip}</p>
        <p className="muted">
          Este módulo llega a la web más adelante; hoy se usa en la ventana de Qt.
        </p>
        {view.error !== null && (
          <p role="alert" className="error">
            {view.error}
          </p>
        )}
      </main>
    </div>
  );
}
