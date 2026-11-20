import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AgentBudget } from "../../api/types";
import ContextBar from "./ContextBar";

const BUDGET: AgentBudget = {
  parts: [
    { key: "rules", label: "Reglas y perfil", chars: 2400, tokens: 1558, limit_chars: null },
    { key: "history", label: "Historial", chars: 162, tokens: 69, limit_chars: 12000 },
  ],
  estimated_tokens: 1627,
  window: null,
  level: "warning",
  summary: "~1,6 k tokens (ventana sin medir: se mide en el primer envío)",
  short_summary: "~1,6 k tokens (ventana sin medir)",
  last_summary: "",
  last: null,
  first_text_s: null,
};

describe("ContextBar", () => {
  it("muestra el resumen y al abrirla el desglose por partes", () => {
    render(<ContextBar budget={BUDGET} />);
    const toggle = screen.getByRole("button", { name: /Uso del contexto/ });
    expect(screen.getByText("~1,6 k tokens (ventana sin medir)")).toHaveAttribute(
      "data-level",
      "warning",
    );
    expect(screen.queryByRole("region", { name: "Lo que se envía a Claude" })).toBeNull();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: "Lo que se envía a Claude" })).toBeVisible();
    expect(screen.getByText("~69 tok · 162 / 12.000 car.")).toBeVisible();
    expect(screen.getByText("Sin envíos todavía: la cifra es una estimación.")).toBeVisible();
  });
});
