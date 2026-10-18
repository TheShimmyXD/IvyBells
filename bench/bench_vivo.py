"""
Banco del motor en vivo: alimenta una grabación a ritmo real y mide la latencia.

Uso (desde la raíz del proyecto):
    .venv/bin/python -m bench.bench_vivo
    .venv/bin/python -m bench.bench_vivo --seconds 30
    .venv/bin/python -m bench.bench_vivo --sources ellos --partial-interval 0.5

Las pistas elegidas ("ellos" = sonido, "tu" = micrófono; las dos por defecto) entran intercaladas en bloques de
100 ms, como llegarían de la captura. La latencia final se mide desde que el VAD cierra
la frase (el bloque con ese audio ya se entregó) hasta que el motor emite el texto final.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from core.bench_metrics import median_s, percentile
from core.engine import TranscriptEvent
from logging_config import LOG_FORMAT
from paths import BENCH_RESULTS_DIR, RECORDINGS_DIR, ROOT, TRANSCRIPTS_DIR

logger = logging.getLogger("bench_vivo")

CHUNK_S = 0.1
SAMPLE_RATE = 16000
# Fuente del motor -> sufijo del archivo en grabaciones/.
TRACKS = {"ellos": "sonido", "tu": "microfono"}


class _Recorder:
    """Guarda cada evento con la hora de pared en que llegó."""

    def __init__(self) -> None:
        self.t0 = 0.0
        self.received: list[tuple[float, TranscriptEvent]] = []

    def __call__(self, event: TranscriptEvent) -> None:
        self.received.append((time.perf_counter() - self.t0, event))
        if event.is_final:
            logger.info("[%7.2f] %s: %s", event.start_s, event.source, event.text)


def _latency_stats(values: list[float]) -> dict:
    return {
        "mediana": round(median_s(values), 3),
        "p90": round(percentile(values, 0.9), 3),
        "max": round(max(values, default=0.0), 3),
    }


def _summarize(recorder: _Recorder) -> dict:
    finals = [(wall, event) for wall, event in recorder.received if event.is_final]
    final_latencies = [wall - event.end_s for wall, event in finals]
    by_source: dict[str, list[float]] = {}
    for wall, event in finals:
        by_source.setdefault(event.source, []).append(wall - event.end_s)
    first_partial: dict[tuple[str, float], float] = {}
    for wall, event in recorder.received:
        key = (event.source, event.start_s)
        if not event.is_final and key not in first_partial:
            first_partial[key] = wall - event.start_s
    partial_delays = list(first_partial.values())
    return {
        "frases_finales": len(finals),
        "provisionales": sum(1 for _wall, event in recorder.received if not event.is_final),
        "latencia_final_s": {
            **_latency_stats(final_latencies),
            "valores": [round(value, 3) for value in final_latencies],
        },
        "por_fuente": {
            source: {"frases_finales": len(values), **_latency_stats(values)}
            for source, values in sorted(by_source.items())
        },
        "primer_provisional_s": {
            "mediana": round(median_s(partial_delays), 3),
            "p90": round(percentile(partial_delays, 0.9), 3),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Banco del motor en vivo de IvyBells")
    parser.add_argument("--audio-prefix", default=str(RECORDINGS_DIR / "f11b"))
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--seconds", type=float, default=0.0, help="0 = la grabación entera")
    parser.add_argument(
        "--sources", default=",".join(TRACKS), help="pistas separadas por coma: ellos, tu"
    )
    parser.add_argument(
        "--partial-interval", type=float, default=0.0, help="segundos; 0 = el del motor"
    )
    args = parser.parse_args()
    sources = [name.strip() for name in args.sources.split(",") if name.strip()]
    unknown = [name for name in sources if name not in TRACKS]
    if not sources or unknown:
        parser.error(f"--sources acepta {', '.join(TRACKS)}; recibido: {args.sources}")

    from services.service_whisper import reexec_with_cuda_libraries

    reexec_with_cuda_libraries("bench.bench_vivo")
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    from services.service_gpu import gpu_identity
    from services.service_streaming import (
        MAX_PHRASE_S,
        MIN_SILENCE_S,
        PARTIAL_INTERVAL_S,
        create_whisper_engine,
    )
    from services.service_whisper import engine_versions, load_audio

    audios = {
        source: load_audio(Path(f"{args.audio_prefix}_{TRACKS[source]}.wav")) for source in sources
    }
    total = min(len(audio) for audio in audios.values())
    if args.seconds:
        total = min(total, int(args.seconds * SAMPLE_RATE))

    recorder = _Recorder()
    partial_interval_s = args.partial_interval or PARTIAL_INTERVAL_S
    engine = create_whisper_engine(
        recorder, args.model, args.compute_type, partial_interval_s=partial_interval_s
    )
    engine.start()

    step = int(CHUNK_S * SAMPLE_RATE)
    recorder.t0 = time.perf_counter()
    max_lag_s = 0.0
    for start in range(0, total, step):
        # El bloque [start, start + step) existe recién cuando termina de sonar.
        due = (start + step) / SAMPLE_RATE
        wait = due - (time.perf_counter() - recorder.t0)
        if wait > 0:
            time.sleep(wait)
        else:
            max_lag_s = max(max_lag_s, -wait)
        for source, audio in audios.items():
            engine.feed(source, audio[start : start + step])
    engine.stop()

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    report = {
        "fecha": stamp,
        "equipo": gpu_identity(),
        "versiones": engine_versions(),
        "audio": {
            source: f"{Path(args.audio_prefix).name}_{TRACKS[source]}.wav" for source in sources
        },
        "segundos": round(total / SAMPLE_RATE, 2),
        "opciones": {
            "modelo": args.model,
            "compute_type": args.compute_type,
            "bloque_s": CHUNK_S,
            "silencio_cierre_s": MIN_SILENCE_S,
            "intervalo_provisional_s": partial_interval_s,
            "frase_max_s": MAX_PHRASE_S,
        },
        "atraso_max_s": round(max_lag_s, 3),
        **_summarize(recorder),
    }
    BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = BENCH_RESULTS_DIR / f"{stamp}_vivo.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"[{event.start_s:7.2f}] {event.source}: {event.text}"
        for _wall, event in recorder.received
        if event.is_final
    ]
    (TRANSCRIPTS_DIR / f"{stamp}_vivo.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    latency = report["latencia_final_s"]
    logger.info(
        "Resultados en %s: %d frases, latencia final mediana %.2f s, p90 %.2f s, atraso max %.2f s",
        json_path.relative_to(ROOT),
        report["frases_finales"],
        latency["mediana"],
        latency["p90"],
        report["atraso_max_s"],
    )


if __name__ == "__main__":
    main()
