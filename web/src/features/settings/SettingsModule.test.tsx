import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoSettings } from "./demo";
import SettingsModule from "./SettingsModule";
import type { ContextActions } from "./useContexts";
import type { ProfileEditor } from "./useProfiles";
import type { Settings } from "./useSettings";

function fakeProfiles(overrides: Partial<ProfileEditor> = {}): ProfileEditor {
  return {
    current: "demo soporte",
    text: "Eres el asistente de soporte.",
    editable: true,
    loading: false,
    saveState: "saved",
    error: null,
    select: vi.fn(),
    edit: vi.fn(),
    flush: vi.fn(),
    use: vi.fn(),
    create: vi.fn(),
    duplicate: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    ...overrides,
  };
}

function fakeContexts(overrides: Partial<ContextActions> = {}): ContextActions {
  return {
    error: null,
    choose: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    reload: vi.fn(),
    openFolder: vi.fn(),
    openSnapshot: vi.fn(),
    ...overrides,
  };
}

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
    applyProfiles: vi.fn(),
    applyContexts: vi.fn(),
    ...overrides,
  };
}

describe("SettingsModule", () => {
  it("pinta lo guardado: cuenta, modelo, esfuerzo, respaldo y tiempo", () => {
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={fakeSettings()}
      />,
    );
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
    render(
      <SettingsModule contexts={fakeContexts()} profiles={fakeProfiles()} settings={settings} />,
    );
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
    render(
      <SettingsModule contexts={fakeContexts()} profiles={fakeProfiles()} settings={settings} />,
    );
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
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={fakeSettings("?account=login")}
      />,
    );
    expect(screen.getByLabelText("Orden para iniciar sesión").textContent).toContain(
      "claude auth login",
    );
    expect(screen.getByRole("button", { name: "Copiar" })).toBeTruthy();
  });

  it("la pestana Contexto abre la lista de contextos", () => {
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={fakeSettings()}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Contexto" }));
    expect(screen.getByRole("region", { name: "Contextos" })).toBeTruthy();
  });

  it("Perfil: la lista con candado y en uso, y el texto abierto", () => {
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={fakeSettings()}
        firstTab="profile"
      />,
    );
    expect(
      screen.getByRole("button", { name: /ejemplo/ }).querySelector(".profile-lock"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /ventas/ }).textContent).toContain("en uso");
    expect(screen.getByRole("button", { name: "demo soporte" }).getAttribute("aria-current")).toBe(
      "true",
    );
    expect(screen.getByRole("textbox", { name: "Texto del perfil" })).toHaveProperty(
      "value",
      "Eres el asistente de soporte.",
    );
    expect(screen.getByRole("status").textContent).toBe("Guardado");
  });

  it("Perfil: escribir, elegir, usar, copiar y crear piden lo suyo", () => {
    const profiles = fakeProfiles();
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={profiles}
        settings={fakeSettings()}
        firstTab="profile"
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Texto del perfil" }), {
      target: { value: "Breve." },
    });
    fireEvent.click(screen.getByRole("button", { name: /ventas/ }));
    fireEvent.click(screen.getByRole("button", { name: "Usar en el Agente" }));
    fireEvent.click(screen.getByRole("button", { name: "Copiar" }));
    fireEvent.click(screen.getByRole("button", { name: "Perfil nuevo" }));
    expect(profiles.edit).toHaveBeenCalledWith("Breve.");
    expect(profiles.select).toHaveBeenCalledWith("ventas");
    expect(profiles.use).toHaveBeenCalledTimes(1);
    expect(profiles.duplicate).toHaveBeenCalledTimes(1);
    expect(profiles.create).toHaveBeenCalledTimes(1);
  });

  it("Perfil: renombrar con Enter y borrar solo tras confirmar", () => {
    const profiles = fakeProfiles();
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={profiles}
        settings={fakeSettings()}
        firstTab="profile"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Renombrar" }));
    const field = screen.getByRole("textbox", { name: "Nombre nuevo del perfil" });
    fireEvent.change(field, { target: { value: "soporte" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(profiles.rename).toHaveBeenCalledWith("soporte");
    fireEvent.click(screen.getByRole("button", { name: "Borrar" }));
    expect(profiles.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole("button", { name: "Borrar" })[1]);
    expect(profiles.remove).toHaveBeenCalledTimes(1);
  });

  it("Perfil de solo lectura: sin renombrar ni borrar, y lo dice", () => {
    const profiles = fakeProfiles({ current: "ejemplo", editable: false });
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={profiles}
        settings={fakeSettings()}
        firstTab="profile"
      />,
    );
    expect(screen.getByRole("button", { name: "Renombrar" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Borrar" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("status").textContent).toContain("Solo lectura");
    expect(screen.getByText(/cópialo para tener uno tuyo/)).toBeTruthy();
  });

  it("Contexto: lista, peso por archivo y aviso de la foto", () => {
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={fakeSettings()}
        firstTab="context"
      />,
    );
    const rows = screen.getByRole("region", { name: "Contextos" });
    expect(rows.textContent).toContain("Sin contexto");
    expect(screen.getByRole("button", { name: /empresa.*en uso/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "empresa" })).toBeTruthy();
    expect(screen.getByText("contextos/empresa")).toBeTruthy();
    expect(screen.getByText("~111 tokens")).toBeTruthy();
    const files = screen.getByRole("list", { name: "Archivos del contexto" });
    expect(files.textContent).toContain("precios.csv40 %~44 tokens");
    expect(screen.getByRole("status").textContent).toContain("2 archivos");
  });

  it("Contexto: cada clic pide su accion", () => {
    const contexts = fakeContexts();
    render(
      <SettingsModule
        contexts={contexts}
        profiles={fakeProfiles()}
        settings={fakeSettings()}
        firstTab="context"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /entrevistas/ }));
    fireEvent.click(screen.getByRole("button", { name: "Sin contexto" }));
    fireEvent.click(screen.getByRole("button", { name: "Contexto nuevo" }));
    fireEvent.click(screen.getByRole("button", { name: "Abrir carpeta" }));
    fireEvent.click(screen.getByRole("button", { name: "Recargar" }));
    fireEvent.click(screen.getByRole("button", { name: "contexto/contexto.md" }));
    fireEvent.click(screen.getByRole("button", { name: "Renombrar" }));
    const field = screen.getByRole("textbox", { name: "Nombre nuevo del contexto" });
    fireEvent.change(field, { target: { value: "clientes" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(contexts.choose).toHaveBeenNthCalledWith(1, "entrevistas");
    expect(contexts.choose).toHaveBeenNthCalledWith(2, "");
    expect(contexts.create).toHaveBeenCalledTimes(1);
    expect(contexts.openFolder).toHaveBeenCalledTimes(1);
    expect(contexts.reload).toHaveBeenCalledTimes(1);
    expect(contexts.openSnapshot).toHaveBeenCalledTimes(1);
    expect(contexts.rename).toHaveBeenCalledWith("empresa", "clientes");
  });

  it("Contexto: recargando, el boton queda apagado; sin contexto, lo dice", () => {
    const settings = fakeSettings();
    const view = settings.view!;
    const busy = {
      ...settings,
      view: { ...view, contextNotice: { text: "Leyendo el contexto...", level: "busy" as const } },
    };
    const { unmount } = render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={busy}
        firstTab="context"
      />,
    );
    expect(screen.getByRole("button", { name: "Recargando..." })).toHaveProperty("disabled", true);
    unmount();
    const none = { ...settings, view: { ...view, contexts: { ...view.contexts, active: "" } } };
    render(
      <SettingsModule
        contexts={fakeContexts()}
        profiles={fakeProfiles()}
        settings={none}
        firstTab="context"
      />,
    );
    expect(screen.getByText(/el Agente responde solo con las reglas y el perfil/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Abrir carpeta" })).toBeNull();
  });
});
