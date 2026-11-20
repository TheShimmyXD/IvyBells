// Menu desplegable con el tema de la app. En Tauri el <select> nativo abre el menu de
// WebKitGTK, que no toma CSS; este sigue el patron "combobox de solo seleccion" de
// WAI-ARIA: el boton guarda el foco y las flechas mueven la opcion activa.
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import Icon from "./Icon";
import "./dropdown.css";

export interface DropdownOption {
  key: string;
  label: string;
  /** Una linea bajo la etiqueta: para que sirve la opcion. */
  help?: string;
}

interface DropdownProps {
  /** Nombre accesible del boton y de la lista. */
  label: string;
  value: string;
  options: DropdownOption[];
  disabled?: boolean;
  className?: string;
  onChange: (key: string) => void;
}

const OPEN_KEYS = new Set(["ArrowDown", "ArrowUp", "Enter", " "]);

export default function Dropdown({
  label,
  value,
  options,
  disabled = false,
  className = "",
  onChange,
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();
  const shown = open && !disabled;
  const current = options.find((option) => option.key === value);

  useEffect(() => {
    if (!shown) {
      return;
    }
    const onPointer = (event: PointerEvent) => {
      if (!(event.target instanceof Node) || !root.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [shown]);

  const openList = () => {
    setActive(Math.max(0, options.indexOf(current ?? options[0])));
    setOpen(true);
  };
  const choose = (key: string) => {
    setOpen(false);
    if (key !== value) {
      onChange(key);
    }
  };

  const onKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!shown) {
      if (OPEN_KEYS.has(event.key)) {
        event.preventDefault();
        openList();
      }
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((index) => Math.min(Math.max(index + step, 0), options.length - 1));
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const option = options.at(active);
      if (option !== undefined) {
        choose(option.key);
      }
    } else if (event.key === "Escape") {
      // Solo cierra el menu: que no llegue al Esc de la ventana (cancelar el Agente).
      event.stopPropagation();
      setOpen(false);
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div className={`dropdown ${className}`.trim()} ref={root}>
      <button
        type="button"
        role="combobox"
        className="dropdown-button"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={shown}
        aria-controls={listId}
        aria-activedescendant={shown ? `${listId}-${active}` : undefined}
        title={current?.help}
        disabled={disabled}
        onClick={() => (shown ? setOpen(false) : openList())}
        onKeyDown={onKey}
      >
        <span>{current?.label ?? (value || "-")}</span>
        <Icon name="caret-down" size={12} />
      </button>
      {shown && (
        <ul id={listId} role="listbox" aria-label={label} className="dropdown-list">
          {options.map((option, index) => (
            <li
              key={option.key}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={option.key === value}
              data-active={index === active || undefined}
              onPointerEnter={() => setActive(index)}
              onClick={() => choose(option.key)}
            >
              <span className="dropdown-check">
                {option.key === value && <Icon name="check" size={13} />}
              </span>
              <span className="dropdown-label">{option.label}</span>
              {option.help && <span className="dropdown-help">{option.help}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
