import { describe, expect, it } from "vitest";
import { SseReader } from "./sse";

describe("SseReader", () => {
  it("arma un evento partido en dos trozos", () => {
    const reader = new SseReader();
    expect(reader.push('id: 3\nevent: progress\ndata: {"a"')).toEqual([]);
    expect(reader.push(":1}\n\n")).toEqual([{ id: 3, event: "progress", data: '{"a":1}' }]);
  });

  it("ignora los comentarios de espera y lee varios eventos de un trozo", () => {
    const reader = new SseReader();
    const events = reader.push(": sigue\n\nid: 1\ndata: uno\n\nid: 2\nevent: done\ndata: dos\n\n");
    expect(events).toEqual([
      { id: 1, event: "message", data: "uno" },
      { id: 2, event: "done", data: "dos" },
    ]);
  });

  it("acepta fines de linea \\r\\n y junta varias lineas de datos", () => {
    const reader = new SseReader();
    expect(reader.push("data: a\r\ndata: b\r\n\r\n")).toEqual([
      { id: null, event: "message", data: "a\nb" },
    ]);
  });
});
