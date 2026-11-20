import { describe, expect, it } from "vitest";
import type { SourceMenu } from "../../api/types";
import {
  FOLLOW_DEFAULT,
  deviceOptions,
  missingNotice,
  selectedDevice,
  shownDevice,
} from "./sourceMenu";

const MENU: SourceMenu = {
  default: { name: "alsa_input.pci-0000_00_1f.3.analog-stereo", label: "analog-stereo" },
  options: [
    { name: "alsa_input.pci-0000_00_1f.3.analog-stereo", label: "analog-stereo" },
    { name: "mic.usb", label: "mic.usb" },
  ],
  preferred: "mic.usb",
  preferred_label: "mic.usb",
  missing: false,
  resolved: "mic.usb",
};

describe("sourceMenu", () => {
  it("empieza con la predeterminada y lleva el nombre completo solo si difiere", () => {
    const options = deviceOptions(MENU);
    expect(options.map((option) => option.key)).toEqual([
      FOLLOW_DEFAULT,
      "alsa_input.pci-0000_00_1f.3.analog-stereo",
      "mic.usb",
    ]);
    expect(options[0].label).toBe("Predeterminada (analog-stereo)");
    expect(options[1].help).toBe("alsa_input.pci-0000_00_1f.3.analog-stereo");
    expect(options[2].help).toBeUndefined();
  });

  it("sin equipos de su tipo no hay menu; sin predeterminada lo dice", () => {
    expect(deviceOptions({ ...MENU, options: [] })).toEqual([]);
    expect(deviceOptions({ ...MENU, default: null })[0].label).toBe("Predeterminada (sin fuente)");
  });

  it("un elegido desconectado marca la predeterminada y avisa sin olvidarlo", () => {
    const gone = { ...MENU, missing: true, resolved: MENU.default?.name ?? null };
    expect(selectedDevice(MENU)).toBe("mic.usb");
    expect(selectedDevice(gone)).toBe(FOLLOW_DEFAULT);
    expect(missingNotice(MENU)).toBeNull();
    expect(missingNotice(gone)).toBe("mic.usb no está conectada: se usa la predeterminada");
  });

  it("la cabecera muestra el equipo que se capturaria", () => {
    expect(shownDevice(MENU)).toBe("mic.usb");
    expect(shownDevice({ ...MENU, resolved: null })).toBe("sin fuente");
  });
});
