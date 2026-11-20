// Cabecera de la conversacion: Ellos a la izquierda y Tu a la derecha, cada uno con su
// dispositivo y el interruptor que cierra o abre su canal.
import type { SourceDevices, SourceId } from "../../api/types";
import Icon from "../../shared/Icon";
import type { IconName } from "../../shared/phosphor";

interface ChannelHeaderProps {
  devices: SourceDevices;
  closed: SourceId[];
  onToggle: (source: SourceId) => void;
}

const CHANNELS: { source: SourceId; label: string; icon: IconName }[] = [
  { source: "ellos", label: "Ellos", icon: "speaker-high" },
  { source: "tu", label: "Tú", icon: "microphone" },
];

export default function ChannelHeader({ devices, closed, onToggle }: ChannelHeaderProps) {
  return (
    <div className="live-channels">
      {CHANNELS.map(({ source, label, icon }) => {
        const open = !closed.includes(source);
        const device = devices[source];
        return (
          <div key={source} className="live-channel" data-source={source} data-open={open}>
            <span className="live-channel-icon">
              <Icon name={icon} size={16} />
            </span>
            <span className="live-channel-text">
              <strong>{label}</strong>
              <span className="live-device" title={device?.name}>
                {open ? (device?.label ?? "predeterminada") : "cerrado"}
              </span>
            </span>
            <button
              type="button"
              role="switch"
              className="live-switch"
              aria-checked={open}
              aria-label={`Canal ${label}`}
              title={open ? `Cerrar el canal ${label}` : `Abrir el canal ${label}`}
              onClick={() => onToggle(source)}
            />
          </div>
        );
      })}
    </div>
  );
}
