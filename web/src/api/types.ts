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
