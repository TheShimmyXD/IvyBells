import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoSettings } from "./demo";
import SettingsModule from "./SettingsModule";
import type { Settings } from "./useSettings";

function fakeSettings(search = "?account=ok", overrides: Partial<Settings> = {}): Settings {
  return {
    view: demoSettings(search),
    error: null,
    setModel: vi.fn(),
    setEffort: vi.fn(),
    setFallback: vi.fn(),
    setTimeout: vi.fn(),
    setAccount: vi.fn(),
    check: vi.fn(),
    ...overrides,
  };
}

describe("SettingsModule", () => {
  it("pinta lo guardado: cuenta, modelo, esfuerzo, respaldo y tiempo", () => {
    render(<SettingsModule settings={fakeSettings()} />);
    expect(screen.getByRole("textbox")).toHaveProperty("value", "persona@example.com");
    expect(screen.getByRole("status").textContent).toContain("Sesión activa");
    expect(screen.getByRole("radio", { name: /El más barato/ })).toHaveProperty("checked", true);
    expect(screen.getByRole("radio", { name: "low" })).toHaveProperty("checked", true);
    expect(screen.getByText("Responde más rápido, razona menos")).toBeTruthy();
    expect(screen.getByRole("radio", { name: "ninguno" })).toHaveProperty("checked", true);
    expect(screen.getByRole("radio", { name: "120 s" }).getAttribute("aria-checked")).toBe("true");
  });

  it("cada clic pide su cambio", () => {
    const settings = fakeSettings();
    render(<SettingsModule settings={settings} />);
    fireEvent.click(screen.getByRole("radio", { name: /Equilibrado/ }));
    fireEvent.click(screen.getByRole("radio", { name: "max" }));
    fireEvent.click(screen.getByRole("radio", { name: "opus" }));
    fireEvent.click(screen.getByRole("radio", { name: "300 s" }));
    expect(settings.setModel).toHaveBeenCalledWith("sonnet");
    expect(settings.setEffort).toHaveBeenCalledWith("max");
    expect(settings.setFallback).toHaveBeenCalledWith("opus");
    expect(settings.setTimeout).toHaveBeenCalledWith(300);
  });

  it("el correo se guarda al salir solo si cambio; Comprobar sin cambios comprueba", () => {
    const settings = fakeSettings();
    render(<SettingsModule settings={settings} />);
    const field = screen.getByRole("textbox");
    fireEvent.blur(field);
    expect(settings.setAccount).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Comprobar" }));
    expect(settings.check).toHaveBeenCalledTimes(1);
    fireEvent.change(field, { target: { value: "otra@example.com" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(settings.setAccount).toHaveBeenCalledWith("otra@example.com");
  });

  it("sin sesion muestra la orden para iniciarla", () => {
    render(<SettingsModule settings={fakeSettings("?account=login")} />);
    expect(screen.getByLabelText("Orden para iniciar sesión").textContent).toContain(
      "claude auth login",
    );
    expect(screen.getByRole("button", { name: "Copiar" })).toBeTruthy();
  });

  it("Perfil y Contexto avisan que llegan en el paso siguiente", () => {
    render(<SettingsModule settings={fakeSettings()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Contexto" }));
    expect(screen.getByText(/llega a la web en el paso siguiente/)).toBeTruthy();
  });
});
