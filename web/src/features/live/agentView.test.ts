import { describe, expect, it } from "vitest";
import type { AgentSnapshot, AgentTurn } from "../../api/types";
import { applyAgentEvent, fromAgentSnapshot, sentPhrases } from "./agentView";

const SNAPSHOT: AgentSnapshot = {
  state: "idle",
  status: "",
  mode: "manual",
  speaker: "ellos",
  busy: false,
  start_mark: null,
  sent: { ellos: [], tu: [] },
  budget: null,
  turns: [],
  turn_silence_s: 1.5,
  last_event: 3,
};

function turn(answer: string, done = false): AgentTurn {
  return {
    source: "ellos",
    model: "haiku",
    mode: "manual",
    clock: "10:00:20",
    done_clock: done ? "10:00:24" : "",
    fragment: "[10:00:08] Quería saber el precio.",
    start: { phrase: 1, word: 0 },
    end: { phrase: 1, word: 4 },
    answer,
    error: "",
    cancelled: false,
    done,
    superseded: false,
    first_text_s: done ? 2.1 : null,
  };
}

describe("vista del Agente", () => {
  it("la respuesta crece en su turno y el siguiente se agrega", () => {
    let view = fromAgentSnapshot(SNAPSHOT);
    view = applyAgentEvent(view, 4, { kind: "turns", data: { count: 1, last: turn("Con") } });
    view = applyAgentEvent(view, 5, {
      kind: "turns",
      data: { count: 1, last: turn("Con gusto.", true) },
    });
    expect(view.turns.map((t) => t.answer)).toEqual(["Con gusto."]);
    view = applyAgentEvent(view, 6, { kind: "turns", data: { count: 2, last: turn("Sí") } });
    expect(view.turns.map((t) => t.answer)).toEqual(["Con gusto.", "Sí"]);
    expect(view.lastEvent).toBe(6);
  });

  it("una sesión nueva vacía los turnos", () => {
    let view = fromAgentSnapshot({ ...SNAPSHOT, turns: [turn("Hola", true)] });
    view = applyAgentEvent(view, 4, { kind: "turns", data: { count: 0, last: null } });
    expect(view.turns).toEqual([]);
  });

  it("estado, marcas, modo y presupuesto vacío", () => {
    let view = fromAgentSnapshot(SNAPSHOT);
    view = applyAgentEvent(view, 4, {
      kind: "state",
      data: {
        state: "start_marked",
        status: "Inicio marcado",
        mode: "manual",
        speaker: "ellos",
        busy: false,
      },
    });
    view = applyAgentEvent(view, 5, {
      kind: "marks",
      data: {
        speaker: "ellos",
        start_mark: null,
        sent: {
          ellos: [
            [
              { phrase: 0, word: 0 },
              { phrase: 2, word: 3 },
            ],
          ],
          tu: [],
        },
      },
    });
    view = applyAgentEvent(view, 6, { kind: "mode", data: { mode: "ahead" } });
    view = applyAgentEvent(view, 7, { kind: "budget", data: {} });
    expect(view.state).toBe("start_marked");
    expect(view.mode).toBe("ahead");
    expect(view.budget).toBeNull();
    expect([...sentPhrases(view)]).toEqual([0, 1, 2]);
  });
});
