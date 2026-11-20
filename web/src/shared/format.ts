// Formato de cifras para la pantalla, con coma decimal.

/** Segundos con un decimal: 1.25 -> "1,3 s". */
export function seconds(value: number): string {
  return `${value.toFixed(1).replace(".", ",")} s`;
}
