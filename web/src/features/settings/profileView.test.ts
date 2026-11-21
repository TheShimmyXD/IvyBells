import { describe, expect, it } from "vitest";
import { pickProfile, profileRows, profilesOnly, renamedTo, saveBadge } from "./profileView";

const PROFILES = {
  names: ["ejemplo", "soporte", "ventas"],
  active: "ventas",
  editable: ["soporte", "ventas"],
};

describe("pickProfile", () => {
  it("abre el elegido si sigue en la lista", () => {
    expect(pickProfile(PROFILES, "soporte")).toBe("soporte");
  });

  it("si el elegido ya no esta (borrado o renombrado por fuera), abre el que esta en uso", () => {
    expect(pickProfile(PROFILES, "nadie")).toBe("ventas");
    expect(pickProfile(PROFILES, null)).toBe("ventas");
  });

  it("sin perfil en uso, el primero; sin perfiles, nada", () => {
    expect(pickProfile({ ...PROFILES, active: "" }, null)).toBe("ejemplo");
    expect(pickProfile({ names: [], active: "", editable: [] }, null)).toBe("");
  });
});

describe("profileRows", () => {
  it("marca el que esta en uso y los de solo lectura", () => {
    expect(profileRows(PROFILES)).toEqual([
      { name: "ejemplo", active: false, locked: true },
      { name: "soporte", active: false, locked: false },
      { name: "ventas", active: true, locked: false },
    ]);
  });
});

describe("saveBadge", () => {
  it("un perfil de solo lectura lo dice siempre", () => {
    expect(saveBadge("pending", false)).toEqual({ text: "Solo lectura", tone: "info" });
  });

  it("sigue al guardado", () => {
    expect(saveBadge("saved", true).text).toBe("Guardado");
    expect(saveBadge("pending", true).text).toBe("Sin guardar");
    expect(saveBadge("saving", true).text).toBe("Guardando...");
    expect(saveBadge("error", true).tone).toBe("error");
  });
});

describe("renamedTo", () => {
  it("quita espacios y descarta vacio o sin cambio", () => {
    expect(renamedTo("  empresa ", "ventas")).toBe("empresa");
    expect(renamedTo("   ", "ventas")).toBeNull();
    expect(renamedTo("ventas ", "ventas")).toBeNull();
  });
});

describe("profilesOnly", () => {
  it("deja fuera el nombre que agrega la API", () => {
    expect(profilesOnly({ ...PROFILES, name: "soporte" } as typeof PROFILES)).toEqual(PROFILES);
  });
});
