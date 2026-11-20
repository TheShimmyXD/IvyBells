// Copia de Venona (web/src/api/sse.ts) con su prueba; sube a jacck_common cuando un
// tercer proyecto la repita igual.
// Lector del formato SSE (text/event-stream). El canal de un trabajo pide la cabecera
// Authorization y EventSource no la manda: se lee con fetch y este lector arma los
// eventos con los trozos que van llegando (un evento puede venir partido).

export interface SseEvent {
  /** El ``id:`` del evento; null si no trae. */
  id: number | null;
  event: string;
  data: string;
}

export class SseReader {
  private buffer = "";

  /** Agrega un trozo y devuelve los eventos completos que ya se pueden leer. */
  push(chunk: string): SseEvent[] {
    this.buffer += chunk.replace(/\r\n?/g, "\n");
    const blocks = this.buffer.split("\n\n");
    this.buffer = blocks.pop() ?? "";
    return blocks.map(parseBlock).filter((event): event is SseEvent => event !== null);
  }
}

/** Un bloque entre lineas en blanco; los comentarios (``: sigue``) no son eventos. */
function parseBlock(block: string): SseEvent | null {
  let id: number | null = null;
  let event = "message";
  const data: string[] = [];
  let hasData = false;
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) {
      continue;
    }
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    if (field === "id") {
      const parsed = Number.parseInt(value, 10);
      id = Number.isNaN(parsed) ? null : parsed;
    } else if (field === "event") {
      event = value || "message";
    } else if (field === "data") {
      data.push(value);
      hasData = true;
    }
  }
  return hasData ? { id, event, data: data.join("\n") } : null;
}
