// Codigos de los iconos de Phosphor que usa la web, los de resources/icons/phosphor-regular.json
// (la prueba los compara con ese archivo).
export const PHOSPHOR = {
  waveform: 0xe802,
  robot: 0xe762,
  "sliders-horizontal": 0xe434,
  sun: 0xe472,
  moon: 0xe330,
} as const;

export type IconName = keyof typeof PHOSPHOR;
