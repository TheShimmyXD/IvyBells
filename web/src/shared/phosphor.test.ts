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
});
