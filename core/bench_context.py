"""
Contexto sintético para el banco del Agente: el mismo formato que `contexto.md`, con datos
de una empresa inventada (nunca archivos del autor). Con la misma semilla sale el mismo
texto; la semilla va en las rutas del índice, al principio, para que cada corrida con una
semilla nueva empiece sin caché.
"""

from __future__ import annotations

from core.agent_context import MAX_FILE_CHARS, ContextFile, build_context

# Solo para dimensionar el texto; la cifra real sale del `usage` de cada corrida.
CHARS_PER_TOKEN_GUESS = 3.5
_PLANS = ("básico", "estándar", "premium", "empresarial", "anual", "educativo", "familiar")
_TOPICS = (
    "facturación",
    "instalación",
    "soporte técnico",
    "garantía",
    "envíos",
    "devoluciones",
    "cambio de titular",
    "portabilidad",
    "cobertura",
    "pagos atrasados",
    "promociones",
)
_DAYS = ("lunes a viernes", "lunes a sábado", "todos los días")


def _line(n: int) -> str:
    plan = _PLANS[n % len(_PLANS)]
    topic = _TOPICS[n % len(_TOPICS)]
    days = _DAYS[n % len(_DAYS)]
    return (
        f"- Caso {n}: un cliente del plan {plan} pregunta por {topic}. Se le explica que el "
        f"plan incluye {n % 9 + 1} usuarios, atención de {days} de {7 + n % 3}:00 a "
        f"{18 + n % 4}:00 y un costo de {10 + n % 47} USD al mes; si insiste, se escala al "
        f"área de {topic} con el folio {1000 + n * 7}."
    )


def synthetic_context(tokens: int, seed: str) -> str:
    """Un `contexto.md` de unos `tokens` tokens repartido en archivos de hasta el tope; "" con 0."""
    if tokens <= 0:
        return ""
    target = int(tokens * CHARS_PER_TOKEN_GUESS)
    files: list[ContextFile] = []
    size = 0
    n = 0
    while size < target:
        lines: list[str] = []
        chunk = 0
        while size + chunk < target:
            line = _line(n)
            if chunk + len(line) + 1 > MAX_FILE_CHARS:
                break
            lines.append(line)
            chunk += len(line) + 1
            n += 1
        files.append(
            ContextFile(f"/empresa_{seed}/casos_{len(files) + 1:02d}.md", "\n".join(lines))
        )
        size += chunk
    return build_context(files, [])
