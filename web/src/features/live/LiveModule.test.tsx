import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LiveModule from "./LiveModule";
import { demoView } from "./demo";
import type { LiveListening } from "./useLiveListening";

function live(overrides: Partial<LiveListening> = {}): LiveListening {
  return {
    view: demoView(),
    error: null,
    notice: null,
    model: "large-v3-turbo",
    chooseModel: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    toggleSource: vi.fn(),
    save: vi.fn(),
    ...overrides,
  };
}

describe("LiveModule", () => {
  it("pinta la conversacion con lo provisional al final y la latencia en el pie", () => {
    render(<LiveModule live={live()} agentTab="agent" onAgentTab={vi.fn()} />);
    const items = within(screen.getByRole("list", { name: "Conversación" })).getAllByRole(
      "listitem",
    );
    expect(items.at(-1)).toHaveTextContent("Ah, y otra cosa …");
    expect(screen.getByText(/Latencia/)).toHaveTextContent(/Latencia \d,\d s mediana \d,\d s/);
    expect(screen.getByText("transcripciones/2026-11-19_2008.md")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar .md" })).toBeDisabled();
  });

  it("Detener, los canales y las pestanas avisan lo que pide el usuario", () => {
    const state = live();
    const onTab = vi.fn();
    render(<LiveModule live={state} agentTab="agent" onAgentTab={onTab} />);
    fireEvent.click(screen.getByRole("button", { name: "Detener" }));
    expect(state.stop).toHaveBeenCalledOnce();
    const tu = screen.getByRole("switch", { name: "Canal Tú" });
    expect(tu).toHaveAttribute("aria-checked", "true");
    fireEvent.click(tu);
    expect(state.toggleSource).toHaveBeenCalledWith("tu");
    expect(screen.getByRole("combobox", { name: "Modelo de transcripción" })).toBeDisabled();
    fireEvent.click(screen.getByRole("tab", { name: "Chat" }));
    expect(onTab).toHaveBeenCalledWith("chat");
    expect(screen.getByRole("switch", { name: "Anticipado" })).toBeDisabled();
  });

  it("detenido ofrece Iniciar y el menu de modelos; Guardar pide la ruta", async () => {
    const base = demoView();
    const state = live({ view: { ...base, state: "stopped", status: "Detenido" } });
    const choosePath = vi.fn().mockResolvedValue("/tmp/copia.md");
    render(
      <LiveModule live={state} agentTab="agent" onAgentTab={vi.fn()} choosePath={choosePath} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Iniciar" }));
    expect(state.start).toHaveBeenCalledOnce();
    fireEvent.change(screen.getByRole("combobox", { name: "Modelo de transcripción" }), {
      target: { value: "large-v3-turbo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar .md" }));
    await vi.waitFor(() => expect(state.save).toHaveBeenCalledWith("/tmp/copia.md"));
    expect(choosePath).toHaveBeenCalledWith(base.path);
  });

  it("muestra el aviso del ultimo canal como alerta", () => {
    render(
      <LiveModule
        live={live({ notice: "Queda al menos un canal abierto." })}
        agentTab="agent"
        onAgentTab={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Queda al menos un canal abierto.");
  });
});
