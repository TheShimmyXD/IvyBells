import { describe, expect, it } from "vitest";
import type { ContextsData } from "../../api/types";
import {
  contextRows,
  isReloading,
  noticeTone,
  shortFolder,
  tokensLabel,
  weightBar,
} from "./contextView";

const CONTEXTS: ContextsData = {
  names: ["empresa", "entrevistas"],
  active: "empresa",
  folder: "/home/x/resources/agent/contextos/empresa",
  target: "/home/x/resources/agent/contexto/contexto.md",
  weights: {},
  entries: [
    { name: "precios.csv", tokens: 44, folder: false },
    { name: "actas", tokens: 0, folder: true },
    { name: "servicios.md", tokens: 66, folder: false },
  ],
  busy: false,
};

describe("contextRows", () => {
  it("pone Sin contexto primero y marca el que esta en uso", () => {
    const rows = contextRows(CONTEXTS);
    expect(rows.map((row) => row.label)).toEqual(["Sin contexto", "empresa", "entrevistas"]);
    expect(rows.filter((row) => row.active).map((row) => row.name)).toEqual(["empresa"]);
  });

  it("sin contexto en uso, la primera fila es la activa", () => {
    const rows = contextRows({ ...CONTEXTS, active: "" });
    expect(rows[0]).toEqual({ name: "", label: "Sin contexto", active: true });
  });
});

describe("weightBar", () => {
  it("reparte la barra por tokens y alterna el color", () => {
    const bar = weightBar(CONTEXTS.entries);
    expect(bar.total).toBe(110);
    expect(bar.parts.map((part) => Math.round(part.share))).toEqual([40, 0, 60]);
    expect(bar.parts.map((part) => part.tone)).toEqual(["first", "second", "first"]);
  });

  it("sin tokens no divide por cero", () => {
    const bar = weightBar([{ name: "a.txt", tokens: 0, folder: false }]);
    expect(bar).toEqual({
      total: 0,
      parts: [{ name: "a.txt", tokens: 0, folder: false, share: 0, tone: "first" }],
    });
  });
});

describe("textos", () => {
  it("tokens con miles y el cero explicado", () => {
    expect(tokensLabel(1200)).toBe("~1.200 tokens");
    expect(tokensLabel(0)).toBe("0 (sin leer o vacío)");
  });

  it("carpeta corta en Linux y en Windows", () => {
    expect(shortFolder(CONTEXTS.folder)).toBe("contextos/empresa");
    expect(shortFolder("C:\\a\\contextos\\b\\")).toBe("contextos/b");
    expect(shortFolder(null)).toBe("");
  });

  it("tono del aviso y lectura en curso", () => {
    expect(noticeTone({ text: "x", level: "warning" })).toBe("warning");
    expect(noticeTone({ text: "", level: "" })).toBe("info");
    expect(isReloading(CONTEXTS, { text: "Leyendo el contexto...", level: "busy" })).toBe(true);
    expect(isReloading(CONTEXTS, { text: "ok", level: "ok" })).toBe(false);
  });
});
