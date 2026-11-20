// Tipos de lo que devuelve la API de Python (entrypoints/api/), escritos una sola vez.

/** Puerto y token que entrega la ventana de Tauri (orden api_session de jacck_tauri). */
export interface ApiSession {
  port: number | null;
  token: string;
  error: string | null;
}

export type ThemeName = "light" | "dark";
/** Modulos de la barra de la web (el Agente vive dentro de En vivo). */
export type ModuleId = "live" | "config";

/** Lo que la interfaz lee al abrirse (GET /api/prefs; SHOWN en entrypoints/api/prefs.py). */
export interface Prefs {
  theme?: string;
  module?: string;
  [key: string]: unknown;
}

/** Las claves que la vista guarda con POST /api/prefs (VIEW_PREFS). */
export type ViewPrefKey = "theme" | "module" | "agent_panel" | "live_model";

// -- Escucha en vivo (entrypoints/api/listening.py) -----------------------------------

export type SourceId = "ellos" | "tu";
export const SOURCE_IDS: readonly SourceId[] = ["ellos", "tu"];

/** Estados de domain/transcription/live_state.py. */
export type ListeningStateName = "stopped" | "loading" | "listening" | "stopping" | "error";

export interface TranscriptLine {
  clock: string;
  text: string;
}

export interface SourceTranscript {
  finals: TranscriptLine[];
  partial: TranscriptLine | null;
}

/** Antes de que frase final de su canal se reanudo la escucha y a que hora. */
export interface ResumeMark {
  before: number;
  clock: string;
}

export type ResumeMarks = Record<SourceId, ResumeMark[]>;

/** Un modelo de la escucha (LIVE_MODELS en domain/transcription/live_view.py). */
export interface LiveModel {
  key: string;
  label: string;
  help: string;
}

/** Dispositivo de una fuente: el nombre de PipeWire y el corto de la cabecera. */
export interface DeviceLabel {
  name: string;
  label: string;
}

export type SourceDevices = Partial<Record<SourceId, DeviceLabel>>;

/** GET /api/listening: todo lo que la vista necesita al abrirse. */
export interface ListeningSnapshot {
  state: ListeningStateName;
  status: string;
  message: string;
  model: string;
  models: LiveModel[];
  devices: SourceDevices;
  closed_sources: SourceId[];
  path: string | null;
  transcript: Record<SourceId, SourceTranscript>;
  resumes: ResumeMarks;
  last_event: number;
}

export interface StatePayload {
  ok: boolean;
  state: ListeningStateName;
  status: string;
  message: string;
}

/** Respuesta de POST /api/listening/start: el estado y los dispositivos que se capturan. */
export interface StartAnswer extends StatePayload {
  devices: SourceDevices;
}

export interface PhrasePayload {
  source: SourceId;
  final: boolean;
  clock: string;
  text: string;
  stable_words: number;
}

export interface LatencyPayload {
  last_s: number | null;
  median_s: number | null;
}

/** Un evento del canal de la escucha, ya con su tipo. */
export type ListeningEvent =
  | { kind: "state"; data: StatePayload }
  | { kind: "phrase"; data: PhrasePayload }
  | { kind: "latency"; data: LatencyPayload }
  | {
      kind: "session";
      data: { new: true; path: string } | { new: false; path: string; resumes: ResumeMarks };
    }
  | { kind: "sources"; data: { closed: SourceId[] } }
  | { kind: "saved"; data: { path: string } };

// -- Agente ----------------------------------------------------------------------------

/** Un clic sobre una frase final del interlocutor: inicio o final del rango. */
export interface AgentMark {
  end: boolean;
  /** Posicion de la frase entre las finales del interlocutor. */
  phrase: number;
  /** Caracter dentro de la frase; el rango va por frases completas, asi que basta 0. */
  offset: number;
}

export type AgentMode = "manual" | "ahead";
export type AgentStateName = "idle" | "start_marked" | "sending" | "answered" | "error";

/** Una posicion en el texto del interlocutor: frase y palabra. */
export interface WordPos {
  phrase: number;
  word: number;
}

export interface AgentBrief {
  state: AgentStateName;
  status: string;
  mode: AgentMode;
  speaker: SourceId;
  busy: boolean;
}

export interface AgentMarks {
  speaker: SourceId;
  start_mark: WordPos | null;
  sent: Record<SourceId, [WordPos, WordPos][]>;
}

/** Un envio al Agente y su respuesta tal como va llegando. */
export interface AgentTurn {
  source: SourceId;
  model: string;
  mode: AgentMode;
  clock: string;
  done_clock: string;
  fragment: string;
  start: WordPos | null;
  end: WordPos | null;
  answer: string;
  error: string;
  cancelled: boolean;
  done: boolean;
  superseded: boolean;
  first_text_s: number | null;
}

export interface BudgetPart {
  key: string;
  label: string;
  chars: number;
  tokens: number;
  limit_chars: number | null;
}

export interface AgentBudget {
  parts: BudgetPart[];
  estimated_tokens: number;
  window: number | null;
  first_text_s: number | null;
}

export interface AgentSnapshot extends AgentBrief, AgentMarks {
  budget: AgentBudget | null;
  turns: AgentTurn[];
  last_event: number;
}

export type AgentEvent =
  | { kind: "state"; data: AgentBrief }
  | { kind: "turns"; data: { count: number; last: AgentTurn | null } }
  | { kind: "marks"; data: AgentMarks }
  | { kind: "budget"; data: AgentBudget | Record<string, never> }
  | { kind: "mode"; data: { mode: AgentMode } };
