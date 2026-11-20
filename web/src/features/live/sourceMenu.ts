// El menu de equipo de cada canal, como el combo de la ventana de Qt: primero
// "Predeterminada", que sigue a la del sistema aunque se conecten o desconecten equipos,
// y despues los conectados. Si el elegido no esta, se marca la predeterminada y se avisa.
import type { SourceMenu } from "../../api/types";
import type { DropdownOption } from "../../shared/Dropdown";

/** La opcion que sigue a la predeterminada del sistema. */
export const FOLLOW_DEFAULT = "";

/** Las opciones del menu; vacio si no hay ningun equipo de su tipo. */
export function deviceOptions(menu: SourceMenu): DropdownOption[] {
  if (menu.options.length === 0) {
    return [];
  }
  const fallback = menu.default?.label ?? "sin fuente";
  return [
    { key: FOLLOW_DEFAULT, label: `Predeterminada (${fallback})`, help: "Sigue a la del sistema" },
    ...menu.options.map((device) => ({
      key: device.name,
      label: device.label,
      help: device.name === device.label ? undefined : device.name,
    })),
  ];
}

/** Lo que muestra la cabecera: el equipo que se capturaria, con su nombre corto. */
export function shownDevice(menu: SourceMenu): string {
  const resolved = menu.options.find((device) => device.name === menu.resolved);
  return resolved?.label ?? "sin fuente";
}

/** La opcion marcada: la elegida si esta conectada; si no, la predeterminada. */
export function selectedDevice(menu: SourceMenu): string {
  return menu.missing ? FOLLOW_DEFAULT : menu.preferred;
}

/** El aviso del equipo elegido que no esta conectado; null si no hace falta. */
export function missingNotice(menu: SourceMenu): string | null {
  return menu.missing
    ? `${menu.preferred_label} no está conectada: se usa la predeterminada`
    : null;
}
