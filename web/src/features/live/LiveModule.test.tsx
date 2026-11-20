import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LiveModule from "./LiveModule";
import { demoAgent, demoDevices, demoView, stoppedView } from "./demo";
import type { Agent } from "./useAgent";
import type { LiveListening } from "./useLiveListening";
import type { SourceMenusState } from "./useSourceMenus";

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

  it("el interruptor Anticipado cambia el modo y la ayuda dice como responde", () => {
    const manual = agent({ view: demoAgent("?agent=answered") });
    const { unmount } = render(
      <LiveModule live={live()} agent={manual} agentTab="agent" onAgentTab={vi.fn()} />,
    );
    const toggle = screen.getByRole("switch", { name: "Anticipado" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    fireEvent.click(toggle);
    expect(manual.setMode).toHaveBeenCalledWith("ahead");
    unmount();

    const ahead = agent({ view: demoAgent("?agent=ahead") });
    render(<LiveModule live={live()} agent={ahead} agentTab="agent" onAgentTab={vi.fn()} />);
    const on = screen.getByRole("switch", { name: "Anticipado" });
    expect(on).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Anticipado: escuchando a Ellos")).toBeInTheDocument();
    expect(screen.getByText("1,5 s de silencio")).toBeInTheDocument();
    expect(screen.getByText("envío forzado")).toBeInTheDocument();
    fireEvent.click(on);
    expect(ahead.setMode).toHaveBeenCalledWith("manual");
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
    fireEvent.click(screen.getByRole("combobox", { name: "Modelo de transcripción" }));
    fireEvent.click(screen.getByRole("option", { name: /small/ }));
    expect(state.chooseModel).toHaveBeenCalledWith("small");
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

describe("LiveModule, equipo de cada canal", () => {
  const seeded = demoDevices("?devices=menu");
  const menus = seeded === null ? null : seeded.menus;

  function sources(overrides: Partial<SourceMenusState> = {}): SourceMenusState {
    return { menus, error: null, refresh: vi.fn(), choose: vi.fn(), ...overrides };
  }

  it("detenida, el equipo es un menu: abrirlo relee y elegir avisa la fuente", () => {
    const state = sources();
    render(
      <LiveModule
        live={live({ view: stoppedView(demoView()) })}
        agent={agent()}
        agentTab="agent"
        onAgentTab={vi.fn()}
        sources={state}
      />,
    );
    fireEvent.click(screen.getByRole("combobox", { name: "Equipo de Ellos" }));
    expect(state.refresh).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("option", { name: /usb-Headset_USB-00/ }));
    expect(state.choose).toHaveBeenCalledWith(
      "ellos",
      "alsa_output.usb-Headset_USB-00.analog-stereo.monitor",
    );
    expect(screen.getByRole("combobox", { name: "Equipo de Tú" })).toHaveTextContent(
      "usb-Microfono_USB-00.mono-fallback",
    );
  });

  it("escuchando, el equipo es solo texto", () => {
    render(
      <LiveModule
        live={live()}
        agent={agent()}
        agentTab="agent"
        onAgentTab={vi.fn()}
        sources={sources()}
      />,
    );
    expect(screen.queryByRole("combobox", { name: /Equipo de/ })).toBeNull();
    expect(screen.getByText("analog-stereo.monitor")).toBeInTheDocument();
  });

  it("un error al leer los equipos se muestra como alerta", () => {
    render(
      <LiveModule
        live={live({ view: stoppedView(demoView()) })}
        agent={agent()}
        agentTab="agent"
        onAgentTab={vi.fn()}
        sources={sources({ error: "La API no respondió." })}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("La API no respondió.");
  });
});
