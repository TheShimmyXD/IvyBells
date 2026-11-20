// Los canales del Agente y del chat mandan en cada evento `turns` cuantos hay y el ultimo:
// la lista crece, se reemplaza el ultimo (la respuesta que va llegando) o se vacia.

export function withLast<T>(items: T[], count: number, last: T | null): T[] {
  if (count === 0 || last === null) {
    return [];
  }
  return [...items.slice(0, count - 1), last];
}
