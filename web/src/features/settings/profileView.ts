// Los perfiles del Agente como datos: cual queda abierto, las filas de la lista, el estado
// del guardado y el nombre que se escribio al renombrar. Logica pura, sin React.
import type { ProfilesData } from "../../api/types";

/** Espera tras la ultima tecla antes de guardar el texto del perfil. */
export const SAVE_DELAY_MS = 800;

export type SaveState = "saved" | "pending" | "saving" | "error";

export interface ProfileRow {
  name: string;
  active: boolean;
  locked: boolean;
}

/** El perfil abierto: el elegido si sigue en la lista; si no, el que esta en uso o el primero. */
export function pickProfile(profiles: ProfilesData, wanted: string | null): string {
  if (wanted !== null && profiles.names.includes(wanted)) {
    return wanted;
  }
  if (profiles.names.includes(profiles.active)) {
    return profiles.active;
  }
  return profiles.names[0] ?? "";
}

export function profileRows(profiles: ProfilesData): ProfileRow[] {
  return profiles.names.map((name) => ({
    name,
    active: name === profiles.active,
    locked: !profiles.editable.includes(name),
  }));
}

export interface SaveBadge {
  text: string;
  tone: "info" | "ok" | "error";
}

/** La insignia junto a "Usar en el Agente". */
export function saveBadge(state: SaveState, editable: boolean): SaveBadge {
  if (!editable) {
    return { text: "Solo lectura", tone: "info" };
  }
  switch (state) {
    case "saved":
      return { text: "Guardado", tone: "ok" };
    case "pending":
      return { text: "Sin guardar", tone: "info" };
    case "saving":
      return { text: "Guardando...", tone: "info" };
    case "error":
      return { text: "No se guardó", tone: "error" };
  }
}

/** El nombre nuevo sin espacios de sobra, o null si queda vacio o no cambio. */
export function renamedTo(typed: string, current: string): string | null {
  const name = typed.trim();
  return name === "" || name === current ? null : name;
}

/** Solo los campos de la lista: la API a veces agrega `name` (el perfil que quedo). */
export function profilesOnly(data: ProfilesData): ProfilesData {
  return { names: data.names, active: data.active, editable: data.editable };
}
