// Codigos de los iconos de Phosphor que usa la web, los de resources/icons/phosphor-regular.json
// (la prueba los compara con ese archivo).
export const PHOSPHOR = {
  waveform: 0xe802,
  robot: 0xe762,
  "sliders-horizontal": 0xe434,
  sun: 0xe472,
  moon: 0xe330,
  "speaker-high": 0xe44a,
  microphone: 0xe326,
  stop: 0xe46c,
  play: 0xe3d0,
  "download-simple": 0xe20c,
  clock: 0xe19a,
  "file-text": 0xe23a,
  "arrow-down": 0xe03e,
  "chat-circle": 0xe168,
  lightning: 0xe2de,
} as const;

export type IconName = keyof typeof PHOSPHOR;
