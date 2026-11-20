// Barra de contexto del panel del Agente: la tira por partes con su resumen y, al abrirla,
// lo que se envia a Claude con el detalle de cada parte y la cifra real del ultimo envio.
import { useState } from "react";
import type { AgentBudget } from "../../api/types";
import Icon from "../../shared/Icon";
import { budgetStrip } from "./contextBar";

interface ContextBarProps {
  budget: AgentBudget;
}

interface ContextBarOptions extends ContextBarProps {
  /** Abierta al montar (capturas de la demo con &ctx=open). */
  initiallyOpen?: boolean;
}

function Strip({ budget }: ContextBarProps) {
  const strip = budgetStrip(budget);
  return (
    <span className="ctx-strip" data-measured={strip.measured} aria-hidden="true">
      {strip.segments
        .filter((segment) => segment.visible)
        .map((segment) => (
          <span
            key={segment.key}
            className="ctx-segment"
            data-part={segment.key}
            style={{ width: `${segment.share}%` }}
          />
        ))}
    </span>
  );
}

export default function ContextBar({ budget, initiallyOpen = false }: ContextBarOptions) {
  const [open, setOpen] = useState(initiallyOpen);
  const strip = budgetStrip(budget);
  return (
    <div className="ctx">
      {open && (
        <section className="ctx-detail" aria-label="Lo que se envía a Claude">
          <header>
            <strong>Lo que se envía a Claude</strong>
            <span>{budget.summary}</span>
          </header>
          <Strip budget={budget} />
          <ul>
            {strip.segments.map((segment) => (
              <li key={segment.key}>
                <span className="ctx-swatch" data-part={segment.key} aria-hidden="true" />
                <span>{segment.label}</span>
                <span className="ctx-figure">{segment.detail}</span>
              </li>
            ))}
          </ul>
          <p>
            {budget.last_summary === ""
              ? "Sin envíos todavía: la cifra es una estimación."
              : budget.last_summary}
          </p>
        </section>
      )}
      <button
        type="button"
        className="ctx-toggle"
        aria-expanded={open}
        aria-label={`Uso del contexto: ${budget.short_summary}`}
        title={open ? "Ocultar el desglose" : "Ver qué se envía a Claude"}
        onClick={() => setOpen(!open)}
      >
        <Strip budget={budget} />
        <span className="ctx-summary" data-level={budget.level}>
          {budget.short_summary}
        </span>
        <Icon name={open ? "caret-down" : "caret-up"} size={12} />
      </button>
    </div>
  );
}
