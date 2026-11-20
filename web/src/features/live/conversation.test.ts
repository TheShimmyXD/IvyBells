import { describe, expect, it } from "vitest";
import { toListeningEvent } from "../../api/client";
import type { ListeningEvent, ListeningSnapshot } from "../../api/types";
import { applyEvent, conversation, fromSnapshot, type LiveView } from "./conversation";
import sample from "./fixtures/sse_listening.json";

const EMPTY: ListeningSnapshot = {
  state: "stopped",
  status: "Detenido",
  message: "",
  model: "large-v3-turbo",
  closed_sources: [],
  path: null,
  transcript: { ellos: { finals: [], partial: null }, tu: { finals: [], partial: null } },
  resumes: { ellos: [], tu: [] },
  last_event: 0,
};

/** Los eventos tal como los mando la API sobre la llamada inventada (FW.6). */
function replay(view: LiveView, events: { id: number; event: string; data: unknown }[]) {
  return events.reduce((current, raw) => {
    const event = toListeningEvent(raw.event, raw.data);
    return event === null ? current : applyEvent(current, raw.id, event);
  }, view);
}

function phrase(source: "ellos" | "tu", final: boolean, clock: string, text: string) {
  return { kind: "phrase", data: { source, final, clock, text, stable_words: 0 } } as const;
}

function texts(view: LiveView): string[] {
  return conversation(view).map((bubble) =>
    bubble.kind === "resumed" ? `Reanudada ${bubble.clock}` : `${bubble.source}: ${bubble.text}`,
  );
}

describe("conversation", () => {
  it("intercala por hora los eventos reales de la API sin desordenar cada canal", () => {
    const view = replay(fromSnapshot(EMPTY), sample.events);
    const bubbles = conversation(view);
    expect(bubbles.map((b) => (b.kind === "phrase" ? `${b.source} ${b.clock}` : b.kind))).toEqual([
      "ellos 20:08:58",
      "tu 20:09:01",
      "ellos 20:09:02",
      "ellos 20:09:07",
      "tu 20:09:11",
      "ellos 20:09:13",
      "ellos 20:09:21",
    ]);
    // La muestra deja abierta la ultima de Ellos ("Ah, y otra cosa"): va al final, provisional.
    expect(bubbles.map((b) => b.kind === "phrase" && b.final)).toEqual([
      ...Array(6).fill(true),
      false,
    ]);
    expect(view.state).toBe("stopped");
    expect(view.closed).toEqual([]);
    expect(view.savedCopy).toBe("llamada_soporte.md");
    expect(view.lastEvent).toBe(27);
  });

  it("deja las provisionales al final y las reemplaza al confirmarse", () => {
    let view = applyEvent(fromSnapshot(EMPTY), 1, phrase("ellos", true, "10:00:00", "Hola."));
    view = applyEvent(view, 2, phrase("tu", false, "10:00:02", "Buenas"));
    view = applyEvent(view, 3, phrase("ellos", false, "10:00:03", "Una"));
    expect(texts(view)).toEqual(["ellos: Hola.", "ellos: Una", "tu: Buenas"]);
    expect(conversation(view).at(-1)).toMatchObject({ final: false, key: "tu-partial" });

    view = applyEvent(view, 4, phrase("tu", true, "10:00:02", "Buenas tardes."));
    expect(texts(view)).toEqual(["ellos: Hola.", "tu: Buenas tardes.", "ellos: Una"]);
    // Un final vacio solo borra la provisional.
    view = applyEvent(view, 5, phrase("ellos", true, "10:00:03", "  "));
    expect(texts(view)).toEqual(["ellos: Hola.", "tu: Buenas tardes."]);
  });

  it("pone una Reanudada por hora antes de la primera frase posterior de cualquier canal", () => {
    let view = fromSnapshot({
      ...EMPTY,
      transcript: {
        ellos: {
          finals: [
            { clock: "10:00:00", text: "A" },
            { clock: "10:05:10", text: "C" },
          ],
          partial: null,
        },
        tu: {
          finals: [
            { clock: "10:00:05", text: "B" },
            { clock: "10:05:02", text: "D" },
          ],
          partial: null,
        },
      },
      resumes: {
        ellos: [{ before: 1, clock: "10:05" }],
        tu: [{ before: 1, clock: "10:05" }],
      },
    });
    expect(texts(view)).toEqual(["ellos: A", "tu: B", "Reanudada 10:05", "tu: D", "ellos: C"]);

    // Reanudada sin nadie que hable despues: al final, antes de las provisionales.
    const resumed: ListeningEvent = {
      kind: "session",
      data: {
        new: false,
        resumes: {
          ellos: [...view.resumes.ellos, { before: 2, clock: "10:20" }],
          tu: [...view.resumes.tu, { before: 2, clock: "10:20" }],
        },
      },
    };
    view = applyEvent(view, 9, resumed);
    view = applyEvent(view, 10, phrase("tu", false, "10:20:01", "Eh"));
    expect(texts(view).slice(-2)).toEqual(["Reanudada 10:20", "tu: Eh"]);
  });

  it("una sesion nueva empieza en blanco y lo que la vista no usa se ignora", () => {
    let view = applyEvent(fromSnapshot(EMPTY), 1, phrase("ellos", true, "10:00:00", "Hola."));
    view = applyEvent(view, 2, { kind: "session", data: { new: true } });
    expect(conversation(view)).toEqual([]);
    expect(toListeningEvent("closed", {})).toBeNull();
    expect(toListeningEvent("phrase", "texto")).toBeNull();
  });
});
