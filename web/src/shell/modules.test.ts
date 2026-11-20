import { describe, expect, it } from "vitest";
import { DEFAULT_VIEW, MODULES, nextTheme, viewFromPrefs, viewFromQuery } from "./modules";

describe("modules", () => {
  it("tiene los tres modulos de Qt en su orden", () => {
    expect(MODULES.map((entry) => entry.id)).toEqual(["live", "agent", "config"]);
  });

  it("alterna claro y oscuro", () => {
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("light");
  });

  it("toma lo recordado y descarta lo desconocido", () => {
    expect(viewFromPrefs({ theme: "dark", module: "agent" })).toEqual({
      theme: "dark",
      module: "agent",
    });
    expect(viewFromPrefs({ theme: "sepia", module: "mail" })).toEqual(DEFAULT_VIEW);
    expect(viewFromPrefs({})).toEqual(DEFAULT_VIEW);
  });

  it("lee la vista de la URL para las capturas", () => {
    expect(viewFromQuery("?theme=dark&module=config")).toEqual({
      theme: "dark",
      module: "config",
    });
    expect(viewFromQuery("")).toEqual(DEFAULT_VIEW);
  });
});
