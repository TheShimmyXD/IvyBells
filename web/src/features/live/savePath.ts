// Donde guardar la copia del .md: el dialogo nativo de Tauri, igual que en Qt (sugiere
// ~/<nombre del .md de la sesion> y filtra Markdown). En el navegador no hay dialogo y
// Guardar queda apagado.

export const SAVE_TITLE = "Guardar transcripción";

/** Lo que el dialogo propone: la carpeta personal con el nombre del .md actual. */
export function suggestedSavePath(home: string, lastPath: string | null): string {
  if (lastPath === null) {
    return "";
  }
  const name = lastPath.slice(Math.max(lastPath.lastIndexOf("/"), lastPath.lastIndexOf("\\")) + 1);
  const base = home.replace(/[\\/]+$/, "");
  return base === "" ? name : `${base}/${name}`;
}

/** Abre el dialogo de Guardar; ``null`` si el usuario cancela. */
export async function chooseSavePath(lastPath: string | null): Promise<string | null> {
  const [{ save }, { homeDir }] = await Promise.all([
    import("@tauri-apps/plugin-dialog"),
    import("@tauri-apps/api/path"),
  ]);
  return save({
    title: SAVE_TITLE,
    defaultPath: suggestedSavePath(await homeDir(), lastPath),
    filters: [{ name: "Markdown", extensions: ["md"] }],
  });
}
