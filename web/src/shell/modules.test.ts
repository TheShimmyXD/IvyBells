import { describe, expect, it } from "vitest";
import {
  DEFAULT_VIEW,
  MODULES,
  nextTheme,
  viewFromPrefs,
  viewFromQuery,
  wantsDemo,
} from "./modules";

describe("modules", () => {
  it("tiene En vivo y Configuracion", () => {
    expect(MODULES.map((entry) => entry.id)).toEqual(["live", "config"]);
  });

  it("alterna claro y oscuro", () => {
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("light");
  });

  it("toma lo recordado y descarta lo desconocido", () => {
    expect(viewFromPrefs({ theme: "dark", module: "config" })).toEqual({
      theme: "dark",
      module: "config",
    });
    expect(viewFromPrefs({ theme: "sepia", module: "mail" })).toEqual(DEFAULT_VIEW);
    expect(viewFromPrefs({})).toEqual(DEFAULT_VIEW);
  });

  it("el Agente que Qt recuerda como modulo abre En vivo", () => {
    expect(viewFromPrefs({ module: "agent" }).module).toBe("live");
  });

  it("lee la vista de la URL para las capturas", () => {
    expect(viewFromQuery("?theme=dark&module=config")).toEqual({
      theme: "dark",
      module: "config",
    });
    expect(viewFromQuery("")).toEqual(DEFAULT_VIEW);
    expect(wantsDemo("?demo=1&theme=dark")).toBe(true);
    expect(wantsDemo("")).toBe(false);
  });
});
