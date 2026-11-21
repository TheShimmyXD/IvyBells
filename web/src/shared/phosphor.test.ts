import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { PHOSPHOR } from "./phosphor";

describe("PHOSPHOR", () => {
  it("usa los mismos codigos que la fuente de resources/icons", () => {
    const path = resolve(__dirname, "../../../resources/icons/phosphor-regular.json");
    const codes = JSON.parse(readFileSync(path, "utf-8")) as Record<string, string>;
    for (const [name, code] of Object.entries(PHOSPHOR)) {
      expect(parseInt(codes[name], 16), name).toBe(code);
    }
  });

  it("cada icono esta en la fuente recortada de resources/web", () => {
    // Si falla: agregaste un icono; corre .venv/bin/python resources/build_web_fonts.py
    const path = resolve(__dirname, "../../../resources/web/phosphor-ui.json");
    const inFont = new Set(
      (JSON.parse(readFileSync(path, "utf-8")) as string[]).map((c) => parseInt(c, 16)),
    );
    for (const [name, code] of Object.entries(PHOSPHOR)) {
      expect(inFont.has(code), name).toBe(true);
    }
  });
});
