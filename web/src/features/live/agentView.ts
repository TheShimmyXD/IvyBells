// El Agente de la vista En vivo como datos: el estado que arma el snapshot de /api/agent
// y cada evento de su canal. Logica pura, sin React.
import type {
  AgentBrief,
  AgentBudget,
  AgentEvent,
  AgentMarks,
  AgentSnapshot,
  AgentTurn,
} from "../../api/types";

export interface AgentView extends AgentBrief, AgentMarks {
  budget: AgentBudget | null;
  turns: AgentTurn[];
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
