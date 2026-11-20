// La vista En vivo (conversacion en burbujas y Agente al lado) como datos: el estado que arma el snapshot y cada
// evento del canal, y las burbujas de la conversacion. Logica pura, sin React.
import {
  SOURCE_IDS,
  type LatencyPayload,
  type ListeningEvent,
  type ListeningSnapshot,
  type ListeningStateName,
  type LiveModel,
  type ResumeMarks,
  type SourceDevices,
  type SourceId,
  type TranscriptLine,
} from "../../api/types";

export interface LiveView {
  state: ListeningStateName;
  status: string;
  message: string;
  model: string;
  models: LiveModel[];
  devices: SourceDevices;
  closed: SourceId[];
  path: string | null;
  savedCopy: string | null;
  finals: Record<SourceId, TranscriptLine[]>;
  partials: Record<SourceId, TranscriptLine | null>;
  resumes: ResumeMarks;
  latency: LatencyPayload;
  lastEvent: number;
}

export type Bubble =
  | { kind: "phrase"; key: string; source: SourceId; clock: string; text: string; final: boolean }
  | { kind: "resumed"; key: string; clock: string };

const NO_LATENCY: LatencyPayload = { last_s: null, median_s: null };

function emptyResumes(): ResumeMarks {
  return { ellos: [], tu: [] };
}

export function fromSnapshot(snapshot: ListeningSnapshot): LiveView {
  return {
    state: snapshot.state,
    status: snapshot.status,
    message: snapshot.message,
    model: snapshot.model,
    models: [...snapshot.models],
    devices: { ...snapshot.devices },
    closed: [...snapshot.closed_sources],
    path: snapshot.path,
    savedCopy: null,
    finals: {
      ellos: [...snapshot.transcript.ellos.finals],
      tu: [...snapshot.transcript.tu.finals],
    },
    partials: { ellos: snapshot.transcript.ellos.partial, tu: snapshot.transcript.tu.partial },
    resumes: snapshot.resumes ?? emptyResumes(),
    latency: NO_LATENCY,
    lastEvent: snapshot.last_event,
  };
}

/** Lo mismo que LiveTranscript.apply y reset/resume en domain/transcription/live_view.py. */
export function applyEvent(view: LiveView, seq: number, event: ListeningEvent): LiveView {
  const next = { ...view, lastEvent: Math.max(view.lastEvent, seq) };
  switch (event.kind) {
    case "state":
      return { ...next, ...pick(event.data) };
    case "phrase": {
      const { source, final, clock, text } = event.data;
      const line = { clock, text: text.trim() };
      if (final) {
        const finals = line.text ? [...view.finals[source], line] : view.finals[source];
        return {
          ...next,
          finals: { ...view.finals, [source]: finals },
          partials: { ...view.partials, [source]: null },
        };
      }
      return { ...next, partials: { ...view.partials, [source]: line.text ? line : null } };
    }
    case "latency":
      return { ...next, latency: event.data };
    case "session":
      if (event.data.new) {
        return {
          ...next,
          finals: { ellos: [], tu: [] },
          partials: { ellos: null, tu: null },
          resumes: emptyResumes(),
          savedCopy: null,
        };
      }
      return { ...next, partials: { ellos: null, tu: null }, resumes: event.data.resumes };
    case "sources":
      return { ...next, closed: [...event.data.closed] };
    case "saved":
      return { ...next, savedCopy: event.data.path };
  }
}

function pick(data: { state: ListeningStateName; status: string; message: string }) {
  return { state: data.state, status: data.status, message: data.message ?? "" };
}

interface Placed {
  source: SourceId;
  index: number;
  line: TranscriptLine;
}

/** Une los dos canales por hora sin desordenar ninguno (cada uno ya viene en su orden). */
function mergeByClock(finals: Record<SourceId, TranscriptLine[]>): Placed[] {
  const [first, second] = SOURCE_IDS;
  const merged: Placed[] = [];
  let i = 0;
  let j = 0;
  while (i < finals[first].length || j < finals[second].length) {
    const a = finals[first][i];
    const b = finals[second][j];
    // A la misma hora va primero Ellos (el orden de SOURCE_IDS).
    if (b === undefined || (a !== undefined && a.clock <= b.clock)) {
      merged.push({ source: first, index: i, line: a });
      i += 1;
    } else {
      merged.push({ source: second, index: j, line: b });
      j += 1;
    }
  }
  return merged;
}

/** Donde va cada Reanudada: antes de la primera frase posterior de cualquiera de los dos
 * canales (o al final si nadie hablo despues); una por hora aunque la marquen los dos. */
function resumePositions(view: LiveView, merged: Placed[]): Map<number, string[]> {
  const at = new Map<string, number>();
  for (const source of SOURCE_IDS) {
    for (const mark of view.resumes[source]) {
      const found = merged.findIndex((item) => item.source === source && item.index >= mark.before);
      const position = found === -1 ? merged.length : found;
      at.set(mark.clock, Math.min(at.get(mark.clock) ?? position, position));
    }
  }
  const byPosition = new Map<number, string[]>();
  for (const [clock, position] of [...at].sort((x, y) => x[0].localeCompare(y[0]))) {
    byPosition.set(position, [...(byPosition.get(position) ?? []), clock]);
  }
  return byPosition;
}

/** Las burbujas en orden: finales por hora, cada Reanudada en su sitio y al final las
 * provisionales de cada canal (se reemplazan al confirmarse). */
export function conversation(view: LiveView): Bubble[] {
  const merged = mergeByClock(view.finals);
  const resumes = resumePositions(view, merged);
  const bubbles: Bubble[] = [];
  const pushResumes = (position: number) => {
    for (const clock of resumes.get(position) ?? []) {
      bubbles.push({ kind: "resumed", key: `resumed-${clock}`, clock });
    }
  };
  merged.forEach((item, position) => {
    pushResumes(position);
    bubbles.push({
      kind: "phrase",
      key: `${item.source}-${item.index}`,
      source: item.source,
      clock: item.line.clock,
      text: item.line.text,
      final: true,
    });
  });
  pushResumes(merged.length);
  for (const source of SOURCE_IDS) {
    const partial = view.partials[source];
    if (partial !== null) {
      bubbles.push({ kind: "phrase", key: `${source}-partial`, source, ...partial, final: false });
    }
  }
  return bubbles;
}
