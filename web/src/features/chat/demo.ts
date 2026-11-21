// El chat de ejemplo para las capturas sin API (?demo=1&chat=answered|writing|empty|long). Frases
// inventadas, nunca de una llamada real.
import type { ChatSnapshot, ChatTurn } from "../../api/types";
import { fromChatSnapshot, type ChatView } from "./chatView";

const CHAT_STAGES = ["answered", "writing", "empty", "long"] as const;
type ChatStage = (typeof CHAT_STAGES)[number];

const CHOICES: ChatSnapshot["choices"] = {
  models: [
    { key: "haiku", label: "haiku", help: "El más barato" },
    { key: "sonnet", label: "sonnet", help: "Equilibrado" },
    { key: "opus", label: "opus", help: "El más capaz" },
  ],
  efforts: [
    { key: "", label: "por defecto", help: "El nivel que trae el modelo" },
    { key: "low", label: "low", help: "" },
    { key: "max", label: "max", help: "" },
  ],
};

const FIRST: ChatTurn = {
  clock: "10:04:12",
  request: "Resume lo que pidió el cliente hasta ahora.",
  model: "haiku",
  effort: "",
  answer:
    "El cliente pidió **tres cosas**:\n\n" +
    "1. Una cotización del plan anual con soporte.\n" +
    "2. Saber si la instalación entra en el precio.\n" +
    "3. Una visita técnica la próxima semana.\n\n" +
    "Quedó pendiente confirmar el `número de sedes`.",
  error: "",
  cancelled: false,
  done: true,
  first_text_s: 1.84,
};

const SECOND: ChatTurn = {
  clock: "10:05:30",
  request: "¿Qué le respondo sobre la instalación?",
  model: "haiku",
  effort: "low",
  answer: "Que la instalación básica va incluida y que el cableado extra se cotiza",
  error: "",
  cancelled: false,
  done: false,
  first_text_s: 2.07,
};

/** Respuesta mas alta que el panel: tabla y cita, para ver que el registro desplaza. */
const LONG: ChatTurn = {
  ...FIRST,
  clock: "10:07:02",
  request: "¿Qué planes compararon?",
  answer:
    "Compararon **cuatro planes** por precio y por soporte:\n\n" +
    "| Plan | Precio | Soporte |\n| --- | --- | --- |\n" +
    "| Básico | 20 USD | Correo |\n| Equipo | 45 USD | Chat |\n" +
    "| Empresa | 90 USD | Teléfono |\n| Anual | 900 USD | Dedicado |\n\n" +
    "**Si te piden opinión**, puedes decir algo así:\n\n" +
    "> El plan Empresa cuesta el doble que Equipo, pero suma soporte por teléfono. " +
    "Para tres sedes conviene el Anual: sale más barato que doce meses de Empresa y " +
    "trae un técnico dedicado. Antes de firmar, confirmaría cuántas sedes entran y si " +
    "la instalación va incluida en todas o solo en la principal.\n\n" +
    "Quedó pendiente el `número de sedes` y la fecha de la visita técnica.",
};

function isStage(value: string | null): value is ChatStage {
  return CHAT_STAGES.some((stage) => stage === value);
}

/** El chat de ejemplo; null si la URL no pide uno. */
export function demoChat(search: string): ChatView | null {
  const stage = new URLSearchParams(search).get("chat");
  if (!isStage(stage)) {
    return null;
  }
  const turns = { answered: [FIRST], writing: [FIRST, SECOND], empty: [], long: [FIRST, LONG] }[
    stage
  ];
  return fromChatSnapshot({
    model: "haiku",
    effort: stage === "writing" ? "low" : "",
    sending: stage === "writing",
    turns,
    last_first_text_s: turns.length === 0 ? null : turns[turns.length - 1].first_text_s,
    choices: CHOICES,
    last_event: 0,
  });
}

/** Demo: abrir el panel en la pestana Chat (?panel=chat). */
export function demoChatTab(search: string): boolean {
  return new URLSearchParams(search).get("panel") === "chat";
}
