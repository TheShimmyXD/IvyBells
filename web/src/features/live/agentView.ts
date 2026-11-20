// El Agente de la vista En vivo como datos: el estado que arma el snapshot de /api/agent
// y cada evento de su canal. Logica pura, sin React.
import type {
  AgentBrief,
  AgentStateName,
  AgentBudget,
  AgentEvent,
  AgentMarks,
  AgentSnapshot,
  AgentTurn,
} from "../../api/types";

export interface AgentView extends AgentBrief, AgentMarks {
  budget: AgentBudget | null;
  turns: AgentTurn[];
  turn_silence_s: number;
  lastEvent: number;
}

export function fromAgentSnapshot(snapshot: AgentSnapshot): AgentView {
  const { last_event: lastEvent, turns, ...rest } = snapshot;
  return { ...rest, turns: [...turns], lastEvent };
}

/** El evento `turns` trae cuantos hay y el ultimo: crece, se reemplaza o se vacia. */
function withTurns(turns: AgentTurn[], count: number, last: AgentTurn | null): AgentTurn[] {
  if (count === 0 || last === null) {
    return [];
  }
  const kept = turns.slice(0, count - 1);
  return [...kept, last];
}

/** Sin presupuesto la API manda un objeto vacio. */
function isBudget(data: object): data is AgentBudget {
  return "parts" in data;
}

export function applyAgentEvent(view: AgentView, seq: number, event: AgentEvent): AgentView {
  const next = { ...view, lastEvent: Math.max(view.lastEvent, seq) };
  switch (event.kind) {
    case "state":
      return { ...next, ...event.data };
    case "turns":
      return { ...next, turns: withTurns(view.turns, event.data.count, event.data.last) };
    case "marks":
      return { ...next, ...event.data };
    case "budget":
      return { ...next, budget: isBudget(event.data) ? event.data : null };
    case "mode":
      return { ...next, mode: event.data.mode };
  }
}

/** Las frases del interlocutor ya enviadas, para resaltarlas (por frases completas). */
export function sentPhrases(view: AgentView): Set<number> {
  const phrases = new Set<number>();
  for (const [start, end] of view.sent[view.speaker]) {
    for (let phrase = start.phrase; phrase <= end.phrase; phrase += 1) {
      phrases.add(phrase);
    }
  }
  return phrases;
}

export type PhraseMark = "start" | "flight" | "sent";

/**
 * Como se ve cada frase final del interlocutor: inicio marcado, enviada y todavia sin
 * respuesta completa (en vuelo) o ya enviada. El inicio pesa mas que lo demas.
 */
export function phraseMarks(view: AgentView): Map<number, PhraseMark> {
  const marks = new Map<number, PhraseMark>();
  for (const phrase of sentPhrases(view)) {
    marks.set(phrase, "sent");
  }
  for (const turn of view.turns) {
    if (turn.done || turn.source !== view.speaker || turn.start === null || turn.end === null) {
      continue;
    }
    for (let phrase = turn.start.phrase; phrase <= turn.end.phrase; phrase += 1) {
      marks.set(phrase, "flight");
    }
  }
  if (view.start_mark !== null) {
    marks.set(view.start_mark.phrase, "start");
  }
  return marks;
}

export interface AnswerBoard {
  /** La respuesta vigente, grande; null si todavia no hay ninguna. */
  card: AgentTurn | null;
  /** Las demas con algo que mostrar, la mas nueva primero. */
  older: AgentTurn[];
}

/** Un turno terminado sin texto ni error (el "-" del anticipado) no se muestra. */
function hasContent(turn: AgentTurn): boolean {
  return turn.answer !== "" || turn.error !== "" || !turn.done;
}

/** Como en Qt: la ultima respuesta no superada va grande; las otras debajo, en Anteriores. */
export function answerBoard(view: AgentView): AnswerBoard {
  const shown = view.turns.filter(hasContent);
  const newestFirst = [...shown].reverse();
  const card = newestFirst.find((turn) => !turn.superseded) ?? null;
  const older = newestFirst.filter((turn) => turn !== card);
  return { card, older };
}

export function seconds(value: number): string {
  return `${value.toFixed(1).replace(".", ",")} s`;
}

export interface AgentHelp {
  lead: string;
  keys: [string, string][];
}

/** Lo que se ve sin respuestas todavia: en anticipado responde solo y los clics fuerzan. */
export function agentHelp(view: AgentView | null): AgentHelp {
  if (view?.mode === "ahead") {
    return {
      lead: "Cuando el cliente termina de hablar, la respuesta sale aquí, grande, para leerla en voz alta.",
      keys: [
        [`${seconds(view.turn_silence_s)} de silencio`, "responde"],
        ["Clics", "envío forzado"],
        ["Esc", "cancelar"],
      ],
    };
  }
  return {
    lead: "Marca lo que dijo el cliente y la respuesta sale aquí, grande, para leerla en voz alta.",
    keys: [
      ["Clic izq.", "inicio"],
      ["Clic der.", "final y enviar"],
      ["Esc", "cancelar"],
    ],
  };
}

/** La linea bajo la respuesta grande: como va, el modelo y el primer texto. */
export function turnNote(turn: AgentTurn): string {
  let stage = "Lista";
  if (turn.error !== "") {
    stage = "Error";
  } else if (turn.cancelled) {
    stage = "Cancelada";
  } else if (!turn.done) {
    stage = turn.answer === "" ? "Esperando" : "Escribiendo";
  }
  const parts = [stage, turn.model];
  if (turn.first_text_s !== null) {
    parts.push(`primer texto ${seconds(turn.first_text_s)}`);
  }
  return parts.join(" · ");
}

/** La etiqueta de una respuesta anterior: superada, cancelada o ninguna. */
export function olderTag(turn: AgentTurn): string | null {
  if (turn.superseded) {
    return "superada";
  }
  return turn.cancelled ? "cancelada" : null;
}

/** Esc y Cancelar sirven con un inicio marcado o un envio en curso, como en Qt. */
export function canCancel(state: AgentStateName): boolean {
  return state === "start_marked" || state === "sending";
}

const LINE_CLOCK = /^\[\d{2}:\d{2}:\d{2}\]\s*/;

/** Lo enviado como cita corta: las frases seguidas, sin la hora de cada linea (como Qt). */
export function quoteText(fragment: string): string {
  return fragment
    .split("\n")
    .map((line) => line.replace(LINE_CLOCK, "").trim())
    .filter((line) => line !== "")
    .join(" ");
}
