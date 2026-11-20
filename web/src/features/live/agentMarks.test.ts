import { describe, expect, it } from "vitest";
import { markRequest } from "../../api/client";
import type { ListeningSnapshot, SourceId } from "../../api/types";
import { markFor, type MarkButton } from "./agentMarks";
import { conversation, fromSnapshot, type Bubble } from "./conversation";
import sample from "./fixtures/agent_marks.json";

function sampleBubbles(): Bubble[] {
  const snapshot = {
    state: "stopped",
    status: "",
    message: "",
    model: "small",
    models: [],
    devices: {},
    closed_sources: [],
    path: null,
    transcript: {
      ellos: { finals: sample.finals.ellos, partial: null },
      tu: { finals: sample.finals.tu, partial: { clock: "10:00:20", text: "Mire" } },
    },
    resumes: { ellos: [], tu: [] },
    last_event: 0,
  } as unknown as ListeningSnapshot;
  return conversation(fromSnapshot(snapshot));
}

describe("marcas del Agente", () => {
  it("manda por cada clic lo mismo que la muestra que compara con Qt", () => {
    const bubbles = sampleBubbles();
    const speaker = sample.speaker as SourceId;
    for (const send of sample.sends) {
      const sent = send.clicks.flatMap((click) => {
        const bubble = bubbles.find((b) => b.key === click.bubble);
        expect(bubble, click.bubble).toBeDefined();
        const mark = markFor(bubble as Bubble, speaker, click.button as MarkButton);
        return mark === null ? [] : [markRequest(mark)];
      });
      expect(sent).toEqual(send.requests);
    }
  });

  it("ignora la provisional y el otro canal", () => {
    const bubbles = sampleBubbles();
    const partial = bubbles.find((b) => b.key === "tu-partial") as Bubble;
    expect(markFor(partial, "tu", "left")).toBeNull();
    const other = bubbles.find((b) => b.key === "tu-0") as Bubble;
    expect(markFor(other, "ellos", "right")).toBeNull();
    expect(markFor(other, "tu", "right")).toEqual({ end: true, phrase: 0, offset: 0 });
  });

  it("no marca una Reanudada", () => {
    expect(markFor({ kind: "resumed", key: "r", clock: "10:00" }, "ellos", "left")).toBeNull();
  });
});
