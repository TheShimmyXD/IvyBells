// La vista En vivo sin API (npm run dev con ?demo=1): los eventos reales que mando la API
// sobre la llamada inventada de captura_ui.py (FW.6), para las capturas de la web.
import { toListeningEvent } from "../../api/client";
import type { AgentSnapshot, AgentTurn, ListeningSnapshot } from "../../api/types";
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
    budget: null,
    turns: [demoTurn({})],
    turn_silence_s: 1.5,
    last_event: 0,
  };
  return fromAgentSnapshot({ ...base, ...STAGES[stage] });
}
