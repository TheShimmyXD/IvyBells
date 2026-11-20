import { describe, expect, it } from "vitest";
import type { ChatSnapshot, ChatTurn } from "../../api/types";
import {
  applyChatEvent,
  firstTextLabel,
  fromChatSnapshot,
  sendable,
  turnSetup,
  turnStage,
} from "./chatView";

const TURN: ChatTurn = {
  clock: "10:00:00",
  request: "Resume",
  model: "haiku",
  effort: "",
  answer: "",
  error: "",
  cancelled: false,
  done: false,
  first_text_s: null,
};

const SNAPSHOT: ChatSnapshot = {
  model: "haiku",
  effort: "",
  sending: false,
  turns: [],
  last_first_text_s: null,
  choices: {
    models: [{ key: "haiku", label: "haiku", help: "" }],
    efforts: [
      { key: "", label: "por defecto", help: "" },
      { key: "low", label: "low", help: "" },
    ],
  },
  last_event: 4,
};

describe("chatView", () => {
  it("la respuesta crece con los eventos y Vaciar la deja en cero", () => {
    let view = fromChatSnapshot(SNAPSHOT);
    view = applyChatEvent(view, 5, {
      kind: "turns",
      data: { count: 1, last: TURN, last_first_text_s: null },
    });
    const writing = { ...TURN, answer: "Hola", first_text_s: 1.84 };
    view = applyChatEvent(view, 6, {
      kind: "turns",
      data: { count: 1, last: writing, last_first_text_s: 1.84 },
    });
    expect(view.turns).toEqual([writing]);
    expect(view.lastFirstText).toBe(1.84);
    expect(view.lastEvent).toBe(6);
    view = applyChatEvent(view, 7, {
      kind: "turns",
      data: { count: 0, last: null, last_first_text_s: null },
    });
    expect(view.turns).toEqual([]);
  });

  it("sending y config cambian solo lo suyo", () => {
    let view = fromChatSnapshot(SNAPSHOT);
    view = applyChatEvent(view, 5, { kind: "sending", data: { sending: true } });
    expect(view.sending).toBe(true);
    view = applyChatEvent(view, 6, {
      kind: "config",
      data: { model: "sonnet", effort: "low", sending: true },
    });
    expect([view.model, view.effort, view.choices]).toEqual(["sonnet", "low", SNAPSHOT.choices]);
  });

  it("el primer texto como en Qt", () => {
    expect(firstTextLabel(null)).toBe("Primer texto -");
    expect(firstTextLabel(1.84)).toBe("Primer texto 1,8 s");
  });

  it("el esfuerzo vacio se nombra como en el selector", () => {
    expect(turnSetup(TURN, SNAPSHOT.choices)).toBe("haiku, por defecto");
    expect(turnSetup({ ...TURN, effort: "max" }, SNAPSHOT.choices)).toBe("haiku, max");
  });

  it("cada etapa del turno", () => {
    expect(turnStage(TURN)).toBe("waiting");
    expect(turnStage({ ...TURN, answer: "Ho" })).toBe("writing");
    expect(turnStage({ ...TURN, answer: "Hola", done: true })).toBe("done");
    expect(turnStage({ ...TURN, cancelled: true, done: true })).toBe("cancelled");
    expect(turnStage({ ...TURN, error: "sin red", done: true })).toBe("error");
  });

  it("no se manda texto vacio ni con un envio en curso", () => {
    const view = fromChatSnapshot(SNAPSHOT);
    expect(sendable(view, "  hola \n")).toBe("hola");
    expect(sendable(view, "   ")).toBeNull();
    expect(sendable({ ...view, sending: true }, "hola")).toBeNull();
    expect(sendable(null, "hola")).toBeNull();
  });
});
