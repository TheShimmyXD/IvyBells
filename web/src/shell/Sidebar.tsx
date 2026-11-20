// Barra de modulos plegable, como la de Qt (_00_ui_sidebar.py): plegada solo muestra los
// iconos; al acercar el raton (o con el foco del teclado) se despliega por encima del area
// de trabajo con los rotulos. Arriba va el sello; abajo, el boton del tema.
import type { ModuleId, ThemeName } from "../api/types";
import Icon from "../shared/Icon";
import Seal from "../shared/Seal";
import { MODULES, THEME_ICONS, THEME_TIPS } from "./modules";
import "./Sidebar.css";

interface SidebarProps {
  module: ModuleId;
  theme: ThemeName;
  onChoose: (module: ModuleId) => void;
  onCycleTheme: () => void;
}

export default function Sidebar({ module, theme, onChoose, onCycleTheme }: SidebarProps) {
  return (
    <nav className="sidebar" aria-label="Módulos">
      <div className="sidebar-logo" title="IvyBells">
        <Seal onDark />
      </div>
      {MODULES.map((entry) => (
        <button
          key={entry.id}
          type="button"
          className="sidebar-button"
          title={entry.tip}
          aria-current={entry.id === module ? "page" : undefined}
          onClick={() => onChoose(entry.id)}
        >
          <Icon name={entry.icon} />
          <span className="sidebar-label">{entry.label}</span>
        </button>
      ))}
      <div className="sidebar-gap" />
      <button
        type="button"
        className="sidebar-button"
        title={THEME_TIPS[theme]}
        onClick={onCycleTheme}
      >
        <Icon name={THEME_ICONS[theme]} />
        <span className="sidebar-label">{THEME_TIPS[theme]}</span>
      </button>
    </nav>
  );
}
