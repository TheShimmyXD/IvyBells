// Cabecera de la conversacion: Ellos a la izquierda y Tu a la derecha, cada uno con su
// dispositivo y el interruptor que cierra o abre su canal. Con la escucha detenida, el
// dispositivo es un menu para elegir el equipo; escuchando, solo se muestra.
import type { SourceDevices, SourceId, SourceMenus } from "../../api/types";
import Dropdown from "../../shared/Dropdown";
import Icon from "../../shared/Icon";
import type { IconName } from "../../shared/phosphor";
import { deviceOptions, missingNotice, selectedDevice, shownDevice } from "./sourceMenu";

interface ChannelHeaderProps {
  devices: SourceDevices;
  closed: SourceId[];
  onToggle: (source: SourceId) => void;
  /** Los menus de equipo; sin ellos (o escuchando), el dispositivo es solo texto. */
  menus?: SourceMenus | null;
  editable?: boolean;
  onChooseDevice?: (source: SourceId, name: string) => void;
  onOpenMenu?: () => void;
  /** Demo: el menu de este canal abierto para la captura. */
  openMenu?: SourceId | null;
}

const CHANNELS: { source: SourceId; label: string; icon: IconName }[] = [
  { source: "ellos", label: "Ellos", icon: "speaker-high" },
  { source: "tu", label: "Tú", icon: "microphone" },
];

export default function ChannelHeader(props: ChannelHeaderProps) {
  const { devices, closed, onToggle, menus, editable = false, onChooseDevice } = props;
  return (
    <div className="live-channels">
      {CHANNELS.map(({ source, label, icon }) => {
        const open = !closed.includes(source);
        const device = devices[source];
        const menu = menus?.[source];
        const options = menu === undefined ? [] : deviceOptions(menu);
        const choosing = open && editable && options.length > 0 && onChooseDevice !== undefined;
        return (
          <div key={source} className="live-channel" data-source={source} data-open={open}>
            <span className="live-channel-icon">
              <Icon name={icon} size={16} />
            </span>
            <span className="live-channel-text">
              <strong>{label}</strong>
              {choosing && menu !== undefined ? (
                <span
                  className="live-device-slot"
                  title={missingNotice(menu) ?? undefined}
                  data-missing={menu.missing}
                >
                  <Dropdown
                    className="live-device-menu"
                    label={`Equipo de ${label}`}
                    value={selectedDevice(menu)}
                    options={options}
                    buttonLabel={shownDevice(menu)}
                    startOpen={props.openMenu === source}
                    onOpen={props.onOpenMenu}
                    onChange={(name) => onChooseDevice(source, name)}
                  />
                </span>
              ) : (
                <span className="live-device" title={device?.name}>
                  {open ? (device?.label ?? "predeterminada") : "cerrado"}
                </span>
              )}
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
