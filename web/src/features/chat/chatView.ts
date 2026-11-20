// El chat propio del autor como datos: el estado que arma el snapshot de /api/chat y cada
// evento de su canal, y los textos de cada turno. Logica pura, sin React.
import type { ChatBrief, ChatChoices, ChatEvent, ChatSnapshot, ChatTurn } from "../../api/types";
import { seconds } from "../../shared/format";
import { withLast } from "../../shared/turnList";

export interface ChatView extends ChatBrief {
  turns: ChatTurn[];
  lastFirstText: number | null;
  choices: ChatChoices;
  lastEvent: number;
}

export function fromChatSnapshot(snapshot: ChatSnapshot): ChatView {
  const { last_event: lastEvent, last_first_text_s: lastFirstText, turns, ...rest } = snapshot;
  return { ...rest, turns: [...turns], lastFirstText, lastEvent };
}

export function applyChatEvent(view: ChatView, seq: number, event: ChatEvent): ChatView {
  const next = { ...view, lastEvent: Math.max(view.lastEvent, seq) };
  switch (event.kind) {
    case "turns":
      return {
        ...next,
        turns: withLast(view.turns, event.data.count, event.data.last),
        lastFirstText: event.data.last_first_text_s,
      };
    case "sending":
      return { ...next, sending: event.data.sending };
    case "config":
      return { ...next, ...event.data };
  }
}

/** Como en Qt: "Primer texto 1,8 s", o un guion si ninguna respuesta lo tuvo. */
export function firstTextLabel(value: number | null): string {
  return value === null ? "Primer texto -" : `Primer texto ${seconds(value)}`;
}

/** El modelo y el esfuerzo de un turno con el nombre que muestra el selector. */
export function turnSetup(turn: ChatTurn, choices: ChatChoices): string {
  const effort = choices.efforts.find((choice) => choice.key === turn.effort);
  return `${turn.model}, ${effort?.label ?? turn.effort}`;
}

export type TurnStage = "waiting" | "writing" | "done" | "cancelled" | "error";

export function turnStage(turn: ChatTurn): TurnStage {
  if (turn.error !== "") {
    return "error";
  }
  if (turn.cancelled) {
    return "cancelled";
  }
  if (!turn.done) {
    return turn.answer === "" ? "waiting" : "writing";
  }
  return "done";
}

/** Lo que se puede mandar: el texto sin espacios a los lados, y nada si ya hay un envio. */
export function sendable(view: ChatView | null, text: string): string | null {
  const request = text.trim();
  return view === null || view.sending || request === "" ? null : request;
}
