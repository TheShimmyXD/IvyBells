import { describe, expect, it, vi } from "vitest";
import { chooseSavePath, SAVE_TITLE, suggestedSavePath } from "./savePath";

const save = vi.fn();
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: (options: unknown) => save(options) }));
vi.mock("@tauri-apps/api/path", () => ({ homeDir: () => Promise.resolve("/home/ana/") }));

describe("suggestedSavePath", () => {
  it("propone la carpeta personal con el nombre del .md de la sesion", () => {
    expect(suggestedSavePath("/home/ana", "/x/transcripciones/2026-11-19_1030.md")).toBe(
      "/home/ana/2026-11-19_1030.md",
    );
  });

  it("acepta rutas de Windows y la carpeta con barra final", () => {
    expect(suggestedSavePath("C:\\Users\\ana\\", "C:\\t\\a.md")).toBe("C:\\Users\\ana/a.md");
  });

  it("sin .md todavia no propone nada", () => {
    expect(suggestedSavePath("/home/ana", null)).toBe("");
  });
});

describe("chooseSavePath", () => {
  it("abre el dialogo de Tauri con la sugerencia y el filtro Markdown", async () => {
    save.mockResolvedValueOnce("/home/ana/copia.md");
    await expect(chooseSavePath("/x/b.md")).resolves.toBe("/home/ana/copia.md");
    expect(save).toHaveBeenCalledWith({
      title: SAVE_TITLE,
      defaultPath: "/home/ana/b.md",
      filters: [{ name: "Markdown", extensions: ["md"] }],
    });
  });

  it("devuelve null si el usuario cancela", async () => {
    save.mockResolvedValueOnce(null);
    await expect(chooseSavePath(null)).resolves.toBeNull();
  });
});
