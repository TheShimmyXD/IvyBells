import { describe, expect, it } from "vitest";
import { DEMO_SNAPSHOT } from "./demo";
import {
  accountBadge,
  accountChanged,
  accountInitial,
  applySettingsEvent,
  effortHelp,
  fallbackLabel,
  fromSettingsSnapshot,
  timeoutLabel,
} from "./settingsView";

describe("fromSettingsSnapshot", () => {
  it("toma la cuenta avisada si no se esta comprobando", () => {
    const view = fromSettingsSnapshot({
      ...DEMO_SNAPSHOT,
      account: { text: "Sesión activa", level: "ok", login: "" },
      last_event: 7,
    });
    expect(view.account.level).toBe("ok");
    expect(view.lastEvent).toBe(7);
  });

  it("mientras se comprueba, la cuenta dice que esta comprobando", () => {
    const view = fromSettingsSnapshot({
      ...DEMO_SNAPSHOT,
      account: { text: "Sesión activa", level: "ok", login: "" },
      checking: true,
    });
    expect(accountBadge(view.account)).toEqual({
      text: "Comprobando la cuenta...",
      tone: "info",
      busy: true,
    });
  });
});

describe("applySettingsEvent", () => {
  const view = fromSettingsSnapshot(DEMO_SNAPSHOT);

  it("config reemplaza lo guardado y avanza el numero", () => {
    const next = applySettingsEvent(view, 4, {
      kind: "config",
      data: { ...view.config, model: "opus" },
    });
    expect(next.config.model).toBe("opus");
    expect(next.lastEvent).toBe(4);
  });

  it("un numero viejo no hace retroceder el ultimo visto", () => {
    const next = applySettingsEvent({ ...view, lastEvent: 9 }, 3, {
      kind: "account",
      data: { text: "x", level: "error", login: "" },
    });
    expect(next.lastEvent).toBe(9);
    expect(next.account.level).toBe("error");
  });
});

describe("textos de la pestana Claude", () => {
  it("sin comprobar, la insignia lo dice", () => {
    expect(accountBadge({ text: "", level: "", login: "" }).text).toBe("Sin comprobar");
  });

  it("la inicial sale del correo; vacio es la sesion de siempre", () => {
    expect(accountInitial("persona@example.com")).toBe("P");
    expect(accountInitial("  ")).toBe("?");
  });

  it("el correo cambia solo si difiere sin espacios ni mayusculas", () => {
    expect(accountChanged(" Persona@Example.com ", "persona@example.com")).toBe(false);
    expect(accountChanged("otra@example.com", "persona@example.com")).toBe(true);
  });

  it("la ayuda del esfuerzo es la del nivel o la general si no trae", () => {
    expect(effortHelp(DEMO_SNAPSHOT.choices, "low")).toBe("Responde más rápido, razona menos");
    expect(effortHelp(DEMO_SNAPSHOT.choices, "high")).toBe(
      "Más esfuerzo tarda más en dar el primer texto",
    );
  });

  it("respaldo vacio es ninguno y el tiempo lleva su unidad", () => {
    expect(fallbackLabel("")).toBe("ninguno");
    expect(fallbackLabel("sonnet")).toBe("sonnet");
    expect(timeoutLabel(120)).toBe("120 s");
  });
});
