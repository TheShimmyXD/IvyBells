import { describe, expect, it } from "vitest";
import type { AgentTurn } from "../../api/types";
import {
  answerBoard,
  olderTag,
  phraseMarks,
  quoteText,
  turnNote,
  type AgentView,
} from "./agentView";

function turn(changes: Partial<AgentTurn> = {}): AgentTurn {
  return {
    source: "ellos",
    model: "haiku",
    mode: "manual",
    clock: "10:00:20",
    done_clock: "10:00:24",
    fragment: "Quería saber el precio.",
    start: { phrase: 1, word: 0 },
    end: { phrase: 2, word: 3 },
    answer: "Cuesta diez.",
    error: "",
    cancelled: false,
    done: true,
    superseded: false,
    first_text_s: 2.14,
    ...changes,
  };
}

function view(changes: Partial<AgentView> = {}): AgentView {
  return {
    state: "idle",
    status: "",
    mode: "manual",
    speaker: "ellos",
    busy: false,
    start_mark: null,
    sent: { ellos: [], tu: [] },
    budget: null,
    turns: [],
    lastEvent: 0,
    ...changes,
  };
}

describe("marcas de las frases", () => {
  it("enviada, en vuelo e inicio; el inicio manda", () => {
    const flying = turn({
      start: { phrase: 4, word: 0 },
      end: { phrase: 5, word: 2 },
      done: false,
    });
    const marks = phraseMarks(
      view({
        sent: {
          ellos: [
            [
              { phrase: 1, word: 0 },
              { phrase: 2, word: 3 },
            ],
            [
              { phrase: 4, word: 0 },
              { phrase: 5, word: 2 },
            ],
          ],
          tu: [],
        },
        turns: [turn(), flying],
        start_mark: { phrase: 5, word: 0 },
      }),
    );
    expect([...marks.entries()].sort()).toEqual([
      [1, "sent"],
      [2, "sent"],
      [4, "flight"],
      [5, "start"],
    ]);
  });

  it("los turnos del otro interlocutor no marcan nada", () => {
    const other = turn({ source: "tu", done: false });
    expect(phraseMarks(view({ turns: [other] })).size).toBe(0);
  });
});

describe("respuesta grande y anteriores", () => {
  it("sin turnos no hay tarjeta", () => {
    expect(answerBoard(view())).toEqual({ card: null, older: [] });
  });

  it("la ultima no superada va grande y las otras, la mas nueva primero", () => {
    const first = turn({ clock: "1" });
    const second = turn({ clock: "2" });
    const superseded = turn({ clock: "3", superseded: true });
    const board = answerBoard(view({ turns: [first, second, superseded] }));
    expect(board.card?.clock).toBe("2");
    expect(board.older.map((item) => item.clock)).toEqual(["3", "1"]);
  });

  it("un turno terminado sin texto no se muestra; uno esperando si", () => {
    const empty = turn({ clock: "2", answer: "" });
    const waiting = turn({ clock: "3", answer: "", done: false, first_text_s: null });
    expect(answerBoard(view({ turns: [turn({ clock: "1" }), empty] })).card?.clock).toBe("1");
    expect(answerBoard(view({ turns: [turn(), waiting] })).card?.clock).toBe("3");
  });
});

describe("textos del turno", () => {
  it("dice como va, con el modelo y el primer texto", () => {
    expect(turnNote(turn())).toBe("Lista · haiku · primer texto 2,1 s");
    expect(turnNote(turn({ done: false, answer: "", first_text_s: null }))).toBe(
      "Esperando · haiku",
    );
    expect(turnNote(turn({ done: false, first_text_s: 1.96 }))).toBe(
      "Escribiendo · haiku · primer texto 2,0 s",
    );
    expect(turnNote(turn({ error: "sin red" }))).toBe("Error · haiku · primer texto 2,1 s");
    expect(turnNote(turn({ cancelled: true }))).toBe("Cancelada · haiku · primer texto 2,1 s");
  });

  it("etiqueta las anteriores superadas o canceladas", () => {
    expect(olderTag(turn({ superseded: true }))).toBe("superada");
    expect(olderTag(turn({ cancelled: true }))).toBe("cancelada");
    expect(olderTag(turn())).toBeNull();
  });
});

describe("cita de lo enviado", () => {
  it("une las frases sin la hora de cada linea", () => {
    expect(quoteText("[10:00:08] Quería saber\n[10:00:12] el precio.")).toBe(
      "Quería saber el precio.",
    );
    expect(quoteText("sin hora")).toBe("sin hora");
  });
});
