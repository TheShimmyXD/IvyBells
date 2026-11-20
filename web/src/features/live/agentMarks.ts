// Los clics sobre las burbujas como marcas del Agente: logica pura, sin React.
import type { AgentMark, SourceId } from "../../api/types";
import type { Bubble } from "./conversation";

export type MarkButton = "left" | "right";

/**
 * Clic izquierdo marca el inicio y derecho el final (y envia). Solo cuentan las frases
 * finales del interlocutor elegido: lo provisional cambia y el otro canal no se lee.
 */
export function markFor(bubble: Bubble, speaker: SourceId, button: MarkButton): AgentMark | null {
  if (bubble.kind !== "phrase" || bubble.source !== speaker || bubble.index === null) {
    return null;
  }
  return { end: button === "right", phrase: bubble.index, offset: 0 };
}
