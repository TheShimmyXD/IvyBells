// La vista En vivo sin API (npm run dev con ?demo=1): los eventos reales que mando la API
// sobre la llamada inventada de captura_ui.py (FW.6), para las capturas de la web.
import { toListeningEvent } from "../../api/client";
import type {
  AgentBudget,
  AgentSnapshot,
  AgentTurn,
  ListeningSnapshot,
  SourceId,
  SourceMenus,
} from "../../api/types";
import { fromAgentSnapshot, type AgentView } from "./agentView";
import { applyEvent, fromSnapshot, type LiveView } from "./conversation";
import sample from "./fixtures/sse_listening.json";

const DEMO_SNAPSHOT: ListeningSnapshot = {
  state: "stopped",
  status: "Detenido",
  message: "",
  model: "large-v3-turbo",
  // Los de LIVE_MODELS (domain/transcription/live_view.py).
  models: [
    { key: "small", label: "small", help: "El más rápido (mediana 0,5 s) pero erra más" },
    { key: "medium", label: "medium", help: "Intermedio (mediana 1,3 s)" },
    { key: "large-v3-turbo", label: "turbo", help: "El elegido: mediana 1,8 s y el mejor texto" },
  ],
  devices: {
    ellos: { name: "demo.monitor", label: "analog-stereo.monitor" },
    tu: { name: "demo.mic", label: "usb-microfono.mono" },
  },
  closed_sources: [],
  path: "transcripciones/2026-11-19_2008.md",
  transcript: { ellos: { finals: [], partial: null }, tu: { finals: [], partial: null } },
  resumes: { ellos: [], tu: [] },
  last_event: 0,
};

/** La llamada de ejemplo escuchando, con una frase de Ellos todavia provisional. */
export function demoView(): LiveView {
  const replayed = sample.events.reduce((view, raw) => {
    const event = toListeningEvent(raw.event, raw.data);
    return event === null ? view : applyEvent(view, raw.id, event);
  }, fromSnapshot(DEMO_SNAPSHOT));
  const listening = applyEvent(replayed, 0, {
    kind: "state",
    data: { ok: true, state: "listening", status: "Escuchando", message: "" },
  });
  return applyEvent(listening, 0, {
    kind: "phrase",
    data: {
      source: "ellos",
      final: false,
      clock: "20:09:21",
      text: "Ah, y otra cosa",
      stable_words: 0,
    },
  });
}

// -- Menus de equipo (?demo=1&devices=menu|ellos|tu|missing) ----------------------------

const MONITOR = "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor";
const HEADSET = "alsa_output.usb-Headset_USB-00.analog-stereo.monitor";
const MICROPHONE = "alsa_input.usb-Microfono_USB-00.mono-fallback";
const BUILT_IN = "alsa_input.pci-0000_00_1f.3.analog-stereo";

function device(name: string) {
  return { name, label: name.replace(/^alsa_(input|output)\.(pci-[^.]+\.\d+\.)?/, "") };
}

export interface DemoDevices {
  menus: SourceMenus;
  /** El menu abierto para la captura; null si ninguno. */
  open: SourceId | null;
}

/** Los menus de equipo de ejemplo (con la escucha detenida); null si la URL no los pide. */
export function demoDevices(search: string): DemoDevices | null {
  const stage = new URLSearchParams(search).get("devices");
  if (stage === null || !["menu", "ellos", "tu", "missing"].includes(stage)) {
    return null;
  }
  const missing = stage === "missing";
  return {
    menus: {
      ellos: {
        default: device(MONITOR),
        options: [device(MONITOR), device(HEADSET)],
        preferred: "",
        preferred_label: "",
        missing: false,
        resolved: MONITOR,
      },
      tu: {
        default: device(BUILT_IN),
        options: missing ? [device(BUILT_IN)] : [device(BUILT_IN), device(MICROPHONE)],
        preferred: MICROPHONE,
        preferred_label: device(MICROPHONE).label,
        missing,
        resolved: missing ? BUILT_IN : MICROPHONE,
      },
    },
    open: stage === "ellos" || stage === "tu" ? stage : null,
  };
}

/** La misma vista con la escucha detenida: el equipo solo se elige sin escuchar. */
export function stoppedView(view: LiveView): LiveView {
  return applyEvent(view, 0, {
    kind: "state",
    data: { ok: true, state: "stopped", status: "Detenido", message: "" },
  });
}

// -- Agente de ejemplo (?demo=1&agent=answered|start|sending|ahead) --------------------------

const AGENT_STAGES = ["answered", "start", "sending", "ahead"] as const;
type AgentStage = (typeof AGENT_STAGES)[number];

function demoTurn(changes: Partial<AgentTurn>): AgentTurn {
  return {
    source: "ellos",
    model: "haiku",
    mode: "manual",
    clock: "20:09:00",
    done_clock: "20:09:04",
    fragment: "[20:08:58] Buenas tardes, ¿hablo con soporte?",
    start: { phrase: 0, word: 0 },
    end: { phrase: 0, word: 4 },
    answer: "Buenas tardes, sí, habla con el asistente de soporte. ¿En qué le puedo ayudar?",
    error: "",
    cancelled: false,
    done: true,
    superseded: false,
    first_text_s: 3.4,
    ...changes,
  };
}

const ASKED = demoTurn({
  clock: "20:09:15",
  done_clock: "",
  fragment: [
    "[20:09:02] Sí, mire, contraté el plan empresarial la semana pasada",
    "[20:09:07] y todavía no me llega la factura al correo.",
    "[20:09:13] ¿Me pueden decir cuándo la envían y si puedo pagar con transferencia?",
  ].join("\n"),
  start: { phrase: 1, word: 0 },
  end: { phrase: 3, word: 12 },
  answer: "Entiendo, gracias por avisarnos. La factura del plan empresarial se envía en los",
  done: false,
  first_text_s: 3.1,
});

const STAGES: Record<AgentStage, Partial<AgentSnapshot>> = {
  answered: {
    state: "answered",
    status: "Respuesta lista: clic izquierdo para marcar otro inicio",
  },
  start: {
    state: "start_marked",
    status: "Inicio marcado: clic derecho en el final para enviar (Esc cancela)",
    start_mark: { phrase: 1, word: 0 },
  },
  sending: {
    state: "sending",
    status: "Enviando a haiku...",
    busy: true,
    sent: {
      ellos: [
        [
          { phrase: 0, word: 0 },
          { phrase: 0, word: 4 },
        ],
        [
          { phrase: 1, word: 0 },
          { phrase: 3, word: 12 },
        ],
      ],
      tu: [],
    },
    turns: [demoTurn({}), ASKED],
  },
  ahead: {
    status: "Anticipado: escuchando a Ellos",
    mode: "ahead",
    sent: { ellos: [], tu: [] },
    turns: [],
  },
};

// Lo que devuelve budget_data (entrypoints/api/agent.py) para un envio de ejemplo con haiku.
const DEMO_BUDGET: AgentBudget = {
  parts: [
    { key: "rules", label: "Reglas y perfil", chars: 2400, tokens: 1558, limit_chars: null },
    { key: "context", label: "Contexto", chars: 488, tokens: 209, limit_chars: null },
    { key: "history", label: "Historial", chars: 162, tokens: 69, limit_chars: 12000 },
    { key: "fragment", label: "Fragmento", chars: 171, tokens: 73, limit_chars: null },
  ],
  estimated_tokens: 1909,
  window: 1000000,
  level: "ok",
  summary: "~1,9 k de 1 M tokens (<1 %)",
  short_summary: "~1,9 k de 1 M (<1 %)",
  last_summary: "Último envío: 1,6 k tokens, primer texto 3,4 s, 80 % de caché",
  last: { input_tokens: 1612, cached_tokens: 1290, context_window: 1000000 },
  first_text_s: 3.4,
};

/** Demo con &ctx=open: el desglose de la barra de contexto abierto para la captura. */
export function demoContextOpen(search: string): boolean {
  return new URLSearchParams(search).get("ctx") === "open";
}

function isStage(value: string | null): value is AgentStage {
  return AGENT_STAGES.some((stage) => stage === value);
}

/** El Agente de ejemplo para las capturas; null si la URL no pide uno. */
export function demoAgent(search: string): AgentView | null {
  const stage = new URLSearchParams(search).get("agent");
  if (!isStage(stage)) {
    return null;
  }
  const base: AgentSnapshot = {
    state: "idle",
    status: "Clic izquierdo marca el inicio",
    mode: "manual",
    speaker: "ellos",
    busy: false,
    start_mark: null,
    sent: {
      ellos: [
        [
          { phrase: 0, word: 0 },
          { phrase: 0, word: 4 },
        ],
      ],
      tu: [],
    },
    budget: DEMO_BUDGET,
    turns: [demoTurn({})],
    turn_silence_s: 1.5,
    last_event: 0,
  };
  return fromAgentSnapshot({ ...base, ...STAGES[stage] });
}
