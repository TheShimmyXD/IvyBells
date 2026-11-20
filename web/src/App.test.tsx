import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function answer(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

afterEach(() => {
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("navega por los dos modulos desde la barra", () => {
    render(<App desktop={false} />);
    const nav = screen.getByRole("navigation", { name: "Módulos" });
    expect(within(nav).getAllByRole("button")).toHaveLength(3);
    expect(screen.getByRole("heading", { name: "En vivo" })).toBeInTheDocument();
    expect(screen.getByText(/abre con \?demo=1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Configuración" }));
    expect(screen.getByRole("heading", { name: "Configuración" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Configuración" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("con ?demo=1 muestra la llamada de ejemplo sin API", () => {
    window.history.replaceState(null, "", "/?demo=1");
    render(<App desktop={false} />);
    const list = screen.getByRole("list", { name: "Conversación" });
    expect(within(list).getAllByRole("listitem", { name: "Ellos" }).length).toBeGreaterThan(2);
    expect(within(list).getAllByRole("listitem", { name: "Tú" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("status")).toHaveTextContent("Escuchando");
  });

  it("alterna el tema en el documento", () => {
    render(<App desktop={false} />);
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "Tema: claro" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Tema: oscuro" })).toBeInTheDocument();
  });

  it("en la ventana abre con lo recordado y guarda el modulo elegido", async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      (input) => {
        const path = new URL(String(input)).pathname;
        if (path === "/api/listening/events") {
          return new Promise<Response>(() => undefined);
        }
        return Promise.resolve(answer({ theme: "dark", module: "config" }));
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const connect = () => Promise.resolve({ port: 4321, token: "t", error: null });
    render(<App desktop connect={connect} />);
    expect(await screen.findByRole("heading", { name: "Configuración" })).toBeInTheDocument();
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    fireEvent.click(screen.getByRole("button", { name: "En vivo" }));
    await waitFor(() => {
      const saved = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
      expect(JSON.parse(saved?.[1]?.body as string)).toEqual({
        key: "module",
        value: "live",
      });
    });
  });

  it("si la API no arranca lo dice y la barra sigue navegando", async () => {
    const connect = () => Promise.resolve({ port: null, token: "", error: "Sin Python" });
    render(<App desktop connect={connect} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Sin Python");
    expect(screen.getByRole("button", { name: "Configuración" })).toBeEnabled();
  });
});
