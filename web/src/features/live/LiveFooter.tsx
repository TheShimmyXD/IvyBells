// Pie de En vivo: latencia (la ultima y la mediana), la ruta del .md de esta apertura y
// Guardar .md (una copia donde elija el usuario). Sin `onSave`, Guardar queda apagado.
import type { LatencyPayload } from "../../api/types";
import Icon from "../../shared/Icon";
import { latencyParts, shortPath } from "./liveText";

interface LiveFooterProps {
  latency: LatencyPayload;
  path: string | null;
  savedCopy: string | null;
  onSave?: () => void;
}

export default function LiveFooter({ latency, path, savedCopy, onSave }: LiveFooterProps) {
  const { last, median } = latencyParts(latency);
  return (
    <footer className="live-footer">
      <span className="live-latency" title="Latencia de la última frase final y su mediana">
        <Icon name="clock" size={14} />
        Latencia <strong>{last}</strong> mediana {median}
      </span>
      <span className="live-path" title={path ?? undefined}>
        <Icon name="file-text" size={14} />
        {path === null ? "sin .md todavía" : shortPath(path)}
      </span>
      {savedCopy !== null && (
        <span className="live-saved" title={savedCopy}>
          copia: {shortPath(savedCopy)}
        </span>
      )}
      <button
        type="button"
        className="live-save"
        disabled={onSave === undefined || path === null}
        title={onSave === undefined ? "Guardar llega con el diálogo de la ventana" : undefined}
        onClick={onSave}
      >
        <Icon name="download-simple" size={15} />
        Guardar .md
      </button>
    </footer>
  );
}
