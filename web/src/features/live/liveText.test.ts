import { describe, expect, it } from "vitest";
import { formatSeconds, latencyParts, runAction, shortPath, stateTone } from "./liveText";

describe("liveText", () => {
  it("escribe la latencia con coma y un guion sin frases", () => {
    expect(formatSeconds(1.64)).toBe("1,6 s");
    expect(formatSeconds(null)).toBe("-");
    expect(latencyParts({ last_s: 1.6, median_s: 1.83 })).toEqual({
      last: "1,6 s",
      median: "1,8 s",
    });
  });

  it("acorta la ruta del .md a carpeta y archivo", () => {
    expect(shortPath("/home/a/IvyBells/transcripciones/2026-11-19_2008.md")).toBe(
      "transcripciones/2026-11-19_2008.md",
    );
    expect(shortPath("C:\\datos\\llamada.md")).toBe("datos/llamada.md");
    expect(shortPath("llamada.md")).toBe("llamada.md");
  });

  it("el boton principal sigue a can_start y can_stop", () => {
    expect(runAction("stopped")).toBe("start");
    expect(runAction("error")).toBe("start");
    expect(runAction("loading")).toBe("stop");
    expect(runAction("listening")).toBe("stop");
    expect(runAction("stopping")).toBe("wait");
    expect(stateTone("listening")).toBe("ok");
    expect(stateTone("stopping")).toBe("busy");
  });
});
