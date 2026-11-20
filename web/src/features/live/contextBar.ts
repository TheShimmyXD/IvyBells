// La barra de contexto como datos: el ancho de cada parte y su detalle. Logica pura; las
// cifras y los resumenes llegan hechos de la API (los de la barra de Qt): aqui solo se
// reparten en la tira.
import type { AgentBudget, BudgetPart } from "../../api/types";

export interface BudgetSegment {
  key: string;
  label: string;
  /** Porcentaje de la tira: de la ventana si se midio; si no, del total estimado. */
  share: number;
  /** "~1037 tok - 1.182 car."; el historial con su tope. */
  detail: string;
  /** Ocupa algo: se ve aunque sea minima frente a la ventana. */
  visible: boolean;
}

export interface BudgetStrip {
  segments: BudgetSegment[];
  /** Sin ventana medida la tira se llena por proporciones y va tenue. */
  measured: boolean;
}

/** 12000 -> "12.000", como la barra de Qt. */
export function thousands(value: number): string {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function partDetail(part: BudgetPart): string {
  const chars =
    part.limit_chars === null || part.limit_chars === 0
      ? thousands(part.chars)
      : `${thousands(part.chars)} / ${thousands(part.limit_chars)}`;
  return `~${thousands(part.tokens)} tok · ${chars} car.`;
}

export function budgetStrip(budget: AgentBudget): BudgetStrip {
  const scale = budget.window ?? budget.estimated_tokens;
  return {
    measured: budget.window !== null,
    segments: budget.parts.map((part) => ({
      key: part.key,
      label: part.label,
      share: scale > 0 ? Math.min(100, (100 * part.tokens) / scale) : 0,
      detail: partDetail(part),
      visible: part.tokens > 0,
    })),
  };
}
