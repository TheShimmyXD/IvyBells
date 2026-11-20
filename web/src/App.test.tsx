import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

function answer(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

describe("App", () => {
  it("navega por los tres modulos desde la barra", async () => {
    render(<App desktop={false} />);
    const nav = screen.getByRole("navigation", { name: "Módulos" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Transcripción" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Agente" }));
    expect(screen.getByRole("heading", { name: "Agente" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agente" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "Configuración" }));
    expect(screen.getByRole("heading", { name: "Configuración" })).toBeInTheDocument();
  });

  it("alterna el tema en el documento", async () => {
    render(<App desktop={false} />);
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "Tema: claro" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Tema: oscuro" })).toBeInTheDocument();
  });

  it("en la ventana abre con lo recordado y guarda el modulo elegido", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(answer({ theme: "dark", module: "config" }))
      .mockResolvedValue(answer({}));
    vi.stubGlobal("fetch", fetchMock);
    const connect = () => Promise.resolve({ port: 4321, token: "t", error: null });
    render(<App desktop connect={connect} />);
    expect(await screen.findByRole("heading", { name: "Configuración" })).toBeInTheDocument();
    // El tema se aplica en un efecto, un instante despues del render.
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    fireEvent.click(screen.getByRole("button", { name: "Transcripción" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({ key: "module", value: "live" });
  });

  it("si la API no arranca lo dice y la barra sigue navegando", async () => {
    const connect = () => Promise.resolve({ port: null, token: "", error: "Sin Python" });
    render(<App desktop connect={connect} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Sin Python");
    expect(screen.getByRole("button", { name: "Agente" })).toBeEnabled();
  });
});
