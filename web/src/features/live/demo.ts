// La vista En vivo sin API (npm run dev con ?demo=1): los eventos reales que mando la API
// sobre la llamada inventada de captura_ui.py (FW.6), para las capturas de la web.
import { toListeningEvent } from "../../api/client";
import type { ListeningSnapshot } from "../../api/types";
import { applyEvent, fromSnapshot, type LiveView } from "./conversation";
import sample from "./fixtures/sse_listening.json";

const DEMO_SNAPSHOT: ListeningSnapshot = {
  state: "stopped",
  status: "Detenido",
  message: "",
  model: "large-v3-turbo",
  models: [{ key: "large-v3-turbo", label: "turbo", help: "Ejemplo sin API" }],
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
