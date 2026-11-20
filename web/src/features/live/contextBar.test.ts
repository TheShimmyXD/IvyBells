import { describe, expect, it } from "vitest";
import type { AgentBudget } from "../../api/types";
import { thousands } from "../../shared/format";
import { budgetStrip, partDetail } from "./contextBar";

const PARTS = [
  { key: "rules", label: "Reglas y perfil", chars: 1182, tokens: 1037, limit_chars: null },
  { key: "context", label: "Contexto", chars: 488, tokens: 209, limit_chars: null },
  { key: "history", label: "Historial", chars: 198, tokens: 85, limit_chars: 12000 },
  { key: "fragment", label: "Fragmento", chars: 318, tokens: 136, limit_chars: null },
];

function budget(window: number | null): AgentBudget {
  return {
    parts: PARTS,
    estimated_tokens: 1467,
    window,
    level: "ok",
    summary: "",
    short_summary: "",
    last_summary: "",
    last: null,
    first_text_s: null,
  };
}

describe("thousands", () => {
  it("agrupa con punto como Qt", () => {
    expect(thousands(532)).toBe("532");
    expect(thousands(12000)).toBe("12.000");
    expect(thousands(1000000)).toBe("1.000.000");
  });
});

describe("partDetail", () => {
  it("muestra tokens y caracteres; el historial con su tope", () => {
    expect(partDetail(PARTS[0])).toBe("~1.037 tok · 1.182 car.");
    expect(partDetail(PARTS[2])).toBe("~85 tok · 198 / 12.000 car.");
  });
});

describe("budgetStrip", () => {
  it("sin ventana medida reparte la tira por proporciones", () => {
    const strip = budgetStrip(budget(null));
    expect(strip.measured).toBe(false);
    const total = strip.segments.reduce((sum, segment) => sum + segment.share, 0);
    expect(total).toBeCloseTo(100);
  });

  it("con ventana, cada parte es su fraccion de la ventana", () => {
    const strip = budgetStrip(budget(1_000_000));
    expect(strip.measured).toBe(true);
    expect(strip.segments[0].share).toBeCloseTo(0.1037);
  });

  it("una parte vacia no se pinta", () => {
    const empty = { ...budget(null), parts: [{ ...PARTS[2], chars: 0, tokens: 0 }] };
    const strip = budgetStrip({ ...empty, estimated_tokens: 0 });
    expect(strip.segments[0]).toMatchObject({ share: 0, visible: false });
  });
});
