import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoChat } from "./demo";
import ChatPanel from "./ChatPanel";
import type { Chat } from "./useChat";

function fakeChat(search: string, overrides: Partial<Chat> = {}): Chat {
  return {
    view: demoChat(search),
    error: null,
    send: vi.fn(() => Promise.resolve(true)),
    cancel: vi.fn(),
    clear: vi.fn(),
    setModel: vi.fn(),
    setEffort: vi.fn(),
    ...overrides,
  };
}

describe("ChatPanel", () => {
  it("pinta la peticion y la respuesta en Markdown, sin imagenes", () => {
    const chat = fakeChat("?chat=answered");
    chat.view!.turns[0].answer += "\n\n![logo](https://ejemplo.com/a.png)";
    render(<ChatPanel chat={chat} />);
    const log = screen.getByRole("log", { name: "Chat con Claude" });
    expect(within(log).getByText("Resume lo que pidió el cliente hasta ahora.")).toBeTruthy();
    expect(within(log).getByText("tres cosas").tagName).toBe("STRONG");
    expect(within(log).getAllByRole("listitem")).toHaveLength(3);
    expect(log.querySelector("img")).toBeNull();
    expect(screen.getByText("Primer texto 1,8 s")).toBeTruthy();
  });

  it("vacio dice que ve el chat", () => {
    render(<ChatPanel chat={fakeChat("?chat=empty")} />);
    expect(screen.getByText(/Chat sin perfil/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Vaciar" })).toHaveProperty("disabled", true);
  });

  it("Enter envia y vacia el cuadro; Mayus+Enter no envia", async () => {
    const chat = fakeChat("?chat=answered");
    render(<ChatPanel chat={chat} />);
    const box = screen.getByRole("textbox", { name: "Petición para el chat" });
    fireEvent.change(box, { target: { value: "¿Y el precio?" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(chat.send).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(chat.send).toHaveBeenCalledWith("¿Y el precio?");
    await vi.waitFor(() => expect(box).toHaveProperty("value", ""));
  });

  it("si la API no acepta el envio, el texto se queda", async () => {
    const chat = fakeChat("?chat=answered", { send: vi.fn(() => Promise.resolve(false)) });
    render(<ChatPanel chat={chat} />);
    const box = screen.getByRole("textbox", { name: "Petición para el chat" });
    fireEvent.change(box, { target: { value: "hola" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await vi.waitFor(() => expect(chat.send).toHaveBeenCalled());
    expect(box).toHaveProperty("value", "hola");
  });

  it("mientras llega la respuesta, Cancelar en lugar de Enviar", () => {
    const chat = fakeChat("?chat=writing");
    render(<ChatPanel chat={chat} />);
    expect(screen.queryByRole("button", { name: "Enviar" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(chat.cancel).toHaveBeenCalled();
  });
});
