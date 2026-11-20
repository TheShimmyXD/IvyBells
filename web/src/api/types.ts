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

export type BudgetLevel = "ok" | "warning" | "error";

/** Lo que cobro de verdad el ultimo envio respondido. */
export interface BudgetUsage {
  input_tokens: number;
  cached_tokens: number;
  context_window: number | null;
}

/** Los textos salen del dominio (los mismos de la barra de Qt). */
export interface AgentBudget {
  parts: BudgetPart[];
  estimated_tokens: number;
  window: number | null;
  level: BudgetLevel;
  summary: string;
  short_summary: string;
  last_summary: string;
  last: BudgetUsage | null;
  first_text_s: number | null;
}

export interface AgentSnapshot extends AgentBrief, AgentMarks {
  budget: AgentBudget | null;
  turns: AgentTurn[];
  /** Silencio que cierra un turno del interlocutor en anticipado (TURN_SILENCE_S). */
  turn_silence_s: number;
  last_event: number;
}

export type AgentEvent =
  | { kind: "state"; data: AgentBrief }
  | { kind: "turns"; data: { count: number; last: AgentTurn | null } }
  | { kind: "marks"; data: AgentMarks }
  | { kind: "budget"; data: AgentBudget | Record<string, never> }
  | { kind: "mode"; data: { mode: AgentMode } };

// -- Chat propio del autor ---------------------------------------------------------------

/** Una opcion de un selector, como la arma la API (las mismas listas de Qt). */
export interface ChatChoice {
  key: string;
  label: string;
  help: string;
}

export interface ChatChoices {
  models: ChatChoice[];
  efforts: ChatChoice[];
}

export interface ChatBrief {
  model: string;
  effort: string;
  sending: boolean;
}

/** Una peticion del autor y su respuesta tal como va llegando. */
export interface ChatTurn {
  clock: string;
  request: string;
  model: string;
  effort: string;
  answer: string;
  error: string;
  cancelled: boolean;
  done: boolean;
  first_text_s: number | null;
}

export interface ChatSnapshot extends ChatBrief {
  turns: ChatTurn[];
  /** El primer texto de la ultima respuesta que lo tuvo. */
  last_first_text_s: number | null;
  choices: ChatChoices;
  last_event: number;
}

export type ChatEvent =
  | {
      kind: "turns";
      data: { count: number; last: ChatTurn | null; last_first_text_s: number | null };
    }
  | { kind: "sending"; data: { sending: boolean } }
  | { kind: "config"; data: ChatBrief };

// -- Configuracion de Claude (/api/settings) ---------------------------------------------

/** Lo guardado en app_settings.json (claude); "" en effort y fallback_model = ninguno. */
export interface SettingsConfig {
  model: string;
  effort: string;
  fallback_model: string;
  timeout_s: number;
  account: string;
}

export interface SettingsChoices {
  models: ChatChoice[];
  efforts: ChatChoice[];
  fallbacks: string[];
  timeouts_s: number[];
}

/** "" mientras no se comprobo; "busy" mientras se comprueba. */
export type AccountLevel = "" | "info" | "ok" | "warning" | "error" | "busy";

export interface AccountStatus {
  text: string;
  level: AccountLevel;
  /** La orden para iniciar sesion, o "" si no hace falta. */
  login: string;
}

export interface ProfilesData {
  names: string[];
  active: string;
  editable: string[];
}

/** Un perfil abierto (GET /api/profiles/{name}). */
export interface ProfileText {
  name: string;
  text: string;
  editable: boolean;
}

/** La lista tras crear, copiar, renombrar o guardar; name es el perfil que quedo. */
export type ProfileChange = ProfilesData & { name: string };

/** Un archivo o subcarpeta del contexto en uso, con lo que aporta a la foto. */
export interface ContextEntry {
  name: string;
  tokens: number;
  folder: boolean;
}

export interface ContextsData {
  names: string[];
  active: string;
  folder: string | null;
  target: string;
  /** Tokens estimados por archivo o subcarpeta del contexto en uso. */
  weights: Record<string, number>;
  entries: ContextEntry[];
  busy: boolean;
}

/** Como va la foto contexto.md: "busy" al empezar; al terminar ok, warning, info o error. */
export interface ContextNotice {
  text: string;
  level: "" | "busy" | "ok" | "warning" | "info" | "error";
}

export interface ContextChange extends ContextsData {
  name: string;
}

export interface SettingsSnapshot {
  config: SettingsConfig;
  choices: SettingsChoices;
  account: AccountStatus;
  checking: boolean;
  profiles: ProfilesData;
  contexts: ContextsData;
  context_notice: ContextNotice;
  last_event: number;
}

export type SettingsEvent =
  | { kind: "config"; data: SettingsConfig }
  | { kind: "account"; data: AccountStatus }
  | { kind: "profiles"; data: ProfilesData }
  | { kind: "contexts"; data: ContextsData }
  | { kind: "context_reloaded"; data: ContextNotice };
