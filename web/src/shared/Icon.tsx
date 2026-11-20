// Icono de Phosphor dibujado con su fuente, como en Qt: toma el color del texto.
import { PHOSPHOR, type IconName } from "./phosphor";

interface IconProps {
  name: IconName;
  size?: number;
}

const ICON_STYLE = {
  fontFamily: "Phosphor",
  lineHeight: 1,
  display: "inline-flex",
  flex: "none",
} as const;

export default function Icon({ name, size = 22 }: IconProps) {
  return (
    <span aria-hidden="true" style={{ ...ICON_STYLE, fontSize: size }}>
      {String.fromCodePoint(PHOSPHOR[name])}
    </span>
  );
}
