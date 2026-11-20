import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LiveModule from "./LiveModule";
import { demoAgent, demoView } from "./demo";
import type { Agent } from "./useAgent";
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

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    view: null,
    error: null,
    mark: vi.fn(),
    cancel: vi.fn(),
    setMode: vi.fn(),
    setSpeaker: vi.fn(),
    ...overrides,
  };
}

describe("LiveModule", () => {
  it("pinta la conversacion con lo provisional al final y la latencia en el pie", () => {
    render(<LiveModule live={live()} agent={agent()} agentTab="agent" onAgentTab={vi.fn()} />);
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
    render(<LiveModule live={state} agent={agent()} agentTab="agent" onAgentTab={onTab} />);
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
      <LiveModule
        live={state}
        agent={agent()}
        agentTab="agent"
        onAgentTab={vi.fn()}
        choosePath={choosePath}
      />,
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
        agent={agent()}
        agentTab="agent"
        onAgentTab={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Queda al menos un canal abierto.");
  });
});

function phrase(text: string): HTMLElement {
  const list = screen.getByRole("list", { name: "Conversación" });
  const found = within(list)
    .getAllByRole("listitem")
    .find((item) => item.textContent?.includes(text));
  if (found === undefined) {
    throw new Error(`sin la frase ${text}`);
  }
  return found;
}

describe("Agente en la vista En vivo", () => {
  it("clic izquierdo y derecho sobre Ellos marcan; Tu y lo provisional no", () => {
    const state = agent({ view: demoAgent("?agent=answered") });
    render(<LiveModule live={live()} agent={state} agentTab="agent" onAgentTab={vi.fn()} />);
    fireEvent.click(phrase("contraté el plan"));
    fireEvent.contextMenu(phrase("cuándo la envían"));
    expect(state.mark).toHaveBeenNthCalledWith(1, expect.objectContaining({ index: 1 }), "left");
    expect(state.mark).toHaveBeenNthCalledWith(2, expect.objectContaining({ index: 3 }), "right");
    fireEvent.click(phrase("Déjeme revisar"));
    fireEvent.click(phrase("Ah, y otra cosa"));
    expect(state.mark).toHaveBeenCalledTimes(2);
  });

  it("muestra la respuesta grande con su cita y la marca de lo enviado", () => {
    render(
      <LiveModule
        live={live()}
        agent={agent({ view: demoAgent("?agent=answered") })}
        agentTab="agent"
        onAgentTab={vi.fn()}
      />,
    );
    const answer = screen.getByRole("article", { name: "Respuesta" });
    expect(answer).toHaveTextContent("Buenas tardes, ¿hablo con soporte?");
    expect(answer).toHaveTextContent("habla con el asistente de soporte");
    expect(answer).toHaveTextContent("Lista · haiku · primer texto 3,4 s");
    expect(phrase("hablo con soporte")).toHaveAttribute("data-mark", "sent");
    expect(screen.queryByRole("button", { name: "Cancelar" })).toBeNull();
  });

  it("enviando: burbujas en vuelo, Cancelar y Esc cancelan", () => {
    const state = agent({ view: demoAgent("?agent=sending") });
    render(<LiveModule live={live()} agent={state} agentTab="agent" onAgentTab={vi.fn()} />);
    const panel = screen.getByRole("complementary", { name: "Agente" });
    expect(within(panel).getByText("Enviando a haiku...")).toBeInTheDocument();
    expect(phrase("contraté el plan")).toHaveAttribute("data-mark", "flight");
    expect(screen.getByText("Anteriores")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(state.cancel).toHaveBeenCalledTimes(2);
  });

  it("Esc no hace nada sin inicio marcado ni envio", () => {
    const state = agent({ view: demoAgent("?agent=answered") });
    render(<LiveModule live={live()} agent={state} agentTab="agent" onAgentTab={vi.fn()} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(state.cancel).not.toHaveBeenCalled();
  });

  it("inicio marcado: la burbuja lleva la bandera", () => {
    render(
      <LiveModule
        live={live()}
        agent={agent({ view: demoAgent("?agent=start") })}
        agentTab="agent"
        onAgentTab={vi.fn()}
      />,
    );
    expect(phrase("contraté el plan")).toHaveAttribute("data-mark", "start");
    expect(screen.getByTitle("Inicio marcado")).toBeInTheDocument();
  });
});
