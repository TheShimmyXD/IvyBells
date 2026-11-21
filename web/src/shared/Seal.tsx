// El logo de IvyBells en SVG, sobre una rejilla de 64 (la del logo de Qt). La campana se
// dibuja en su rejilla y se reduce a 0.70 al centro del sello, asi que sus trazos se dividen
// por esa escala para medir lo mismo que el sello.
// Los colores van en style: WebKitGTK no acepta var() en los atributos del SVG.
const BELL_SCALE = 0.7;
const BELL_EDGE = 2.4 / BELL_SCALE;
const BELL_BODY =
  "M15 45 C19 41 18 33 19 27 C20 18 26 14 32 14 C38 14 44 18 45 27 C46 33 45 41 49 45 Z";
const SEAL = { stroke: "var(--color-seal)" };

interface SealProps {
  size?: number;
  /** Sobre la barra lateral oscura la campana va en su tinta. */
  onDark?: boolean;
}

export default function Seal({ size = 34, onDark = false }: SealProps) {
  const ink = onDark ? "var(--color-sidebar-ink)" : "var(--color-brand)";
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="IvyBells">
      <circle cx="32" cy="32" r="29" fill="none" strokeWidth="3" style={SEAL} />
      <circle
        cx="32"
        cy="32"
        r="23.5"
        fill="none"
        strokeWidth="2"
        strokeDasharray="2.2 3.4"
        style={SEAL}
      />
      <g transform={`translate(32 31) scale(${BELL_SCALE}) translate(-32 -32)`}>
        <path
          d={BELL_BODY}
          strokeWidth={BELL_EDGE}
          strokeLinejoin="round"
          style={{ fill: ink, stroke: ink }}
        />
        <line
          x1="32"
          y1="14"
          x2="32"
          y2="9.5"
          strokeWidth={BELL_EDGE}
          strokeLinecap="round"
          style={{ stroke: ink }}
        />
        <circle cx="32" cy="51.5" r="4.6" style={{ fill: "var(--color-seal)" }} />
      </g>
    </svg>
  );
}
