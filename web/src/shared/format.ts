// Formato de cifras para la pantalla, con coma decimal.

/** Segundos con un decimal: 1.25 -> "1,3 s". */
export function seconds(value: number): string {
  return `${value.toFixed(1).replace(".", ",")} s`;
}

/** 12000 -> "12.000", como la barra de Qt. */
export function thousands(value: number): string {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
