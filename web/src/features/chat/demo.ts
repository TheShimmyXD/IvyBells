// El chat de ejemplo para las capturas sin API (?demo=1&chat=answered|writing|empty). Frases
// inventadas, nunca de una llamada real.
import type { ChatSnapshot, ChatTurn } from "../../api/types";
import { fromChatSnapshot, type ChatView } from "./chatView";

const CHAT_STAGES = ["answered", "writing", "empty"] as const;
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

function isStage(value: string | null): value is ChatStage {
  return CHAT_STAGES.some((stage) => stage === value);
}

/** El chat de ejemplo; null si la URL no pide uno. */
export function demoChat(search: string): ChatView | null {
  const stage = new URLSearchParams(search).get("chat");
  if (!isStage(stage)) {
    return null;
  }
  const turns = { answered: [FIRST], writing: [FIRST, SECOND], empty: [] }[stage];
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
