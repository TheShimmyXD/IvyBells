"""Cuentas puras del banco del motor: RTF, VRAM pico, salud del texto y tabla resumen."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

# Un texto con menos de esta fracción de letras (sobre los caracteres no blancos) se marca
# como sospechoso: FP16 en las GTX 16xx puede devolver "!!!!" o símbolos sueltos.
MIN_LETTER_RATIO = 0.6


@dataclass(frozen=True, slots=True)
class TextHealth:
    """Señales baratas de que el motor devolvió texto y no basura. La calidad la juzga el autor."""

    words: int
    letter_ratio: float

    @property
    def looks_broken(self) -> bool:
        return self.words == 0 or self.letter_ratio < MIN_LETTER_RATIO


def real_time_factor(compute_s: float, audio_s: float) -> float:
    """RTF = tiempo de cómputo / duración del audio. Menor que 1 es más rápido que el tiempo real."""
    if audio_s <= 0:
        raise ValueError("La duración del audio debe ser positiva")
    return compute_s / audio_s


def peak_over_baseline(samples_mib: list[int], baseline_mib: int) -> int:
    """VRAM pico propia de la corrida: el máximo muestreado menos lo que ya ocupaba el escritorio."""
    if not samples_mib:
        return 0
    return max(0, max(samples_mib) - baseline_mib)


def median_s(values: list[float]) -> float:
    """Mediana de una lista de tiempos (0.0 si está vacía)."""
    return statistics.median(values) if values else 0.0


def percentile(values: list[float], fraction: float) -> float:
    """Percentil por rango más cercano (fraction=0.9 da el p90). 0.0 si la lista está vacía."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def text_health(text: str) -> TextHealth:
    """Cuenta palabras y la fracción de letras sobre los caracteres no blancos."""
    visible = [char for char in text if not char.isspace()]
    letters = sum(1 for char in visible if char.isalpha())
    ratio = letters / len(visible) if visible else 0.0
    return TextHealth(words=len(text.split()), letter_ratio=ratio)


def pick_window_start(segment_starts: list[float], audio_s: float, window_s: float) -> float:
    """
    Elige dónde empieza la ventana de prueba: el primer segmento con voz que deja una
    ventana completa dentro del audio. Sin segmentos útiles, la mitad del audio.
    """
    for start in segment_starts:
        if start + window_s <= audio_s:
            return start
    return max(0.0, (audio_s - window_s) / 2)


def format_table(rows: list[dict]) -> str:
    """Tabla Markdown con una fila por combinación medida (o con el error si falló)."""
    header = (
        "| Modelo | compute_type | Carga s | RTF sonido | RTF micro | Ventana 5 s | VRAM MiB | Texto |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for row in rows:
        if row.get("error"):
            lines.append(
                f"| {row['model']} | {row['compute_type']} | - | - | - | - | - | "
                f"falla: {row['error'][:60]} |"
            )
            continue
        tracks = row["tracks"]
        broken = any(track["looks_broken"] for track in tracks.values())
        lines.append(
            f"| {row['model']} | {row['compute_type']} | {row['load_s']:.1f} | "
            f"{tracks['sonido']['rtf']:.3f} | {tracks['microfono']['rtf']:.3f} | "
            f"{row['window']['median_s']:.2f} s | {row['vram_peak_mib']} | "
            f"{'sospechoso' if broken else 'ok'} |"
        )
    return "\n".join(lines)
