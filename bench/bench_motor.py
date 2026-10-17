"""
Banco del motor: mide faster-whisper en la GPU local por modelo y compute_type.

Uso (desde la raíz del proyecto):
    .venv/bin/python -m bench.bench_motor
    .venv/bin/python -m bench.bench_motor --models small large-v3-turbo --compute-types int8

Cada combinación corre en un subproceso propio: la VRAM se libera entre corridas y una
falla de la GPU (por ejemplo float16 en una GTX 16xx) no tumba el banco entero.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from core.bench_metrics import (
    format_table,
    median_s,
    peak_over_baseline,
    pick_window_start,
    real_time_factor,
    text_health,
)
from logging_config import LOG_FORMAT
from paths import BENCH_RESULTS_DIR, RECORDINGS_DIR, ROOT, TRANSCRIPTS_DIR

logger = logging.getLogger("bench_motor")

DEFAULT_MODELS = ["small", "medium", "large-v3-turbo", "large-v3"]
DEFAULT_COMPUTE_TYPES = ["float16", "int8_float16", "int8"]
# Pista -> sufijo del archivo en grabaciones/ ("sonido" = Ellos, "microfono" = Tú).
TRACKS = ("sonido", "microfono")
WINDOW_S = 5.0
WARMUP_S = 1.0
# Incluye la descarga del modelo la primera vez (hasta ~3 GB).
COMBO_TIMEOUT_S = 1800


def _run_combo(args: argparse.Namespace, model_name: str, compute_type: str) -> dict:
    """Mide una combinación dentro de este proceso (el hijo) y devuelve su fila."""
    from services.service_gpu import VramSampler, memory_used_mib
    from services.service_whisper import load_audio, load_model, transcribe

    row: dict = {"model": model_name, "compute_type": compute_type}
    audios = {track: load_audio(Path(f"{args.audio_prefix}_{track}.wav")) for track in TRACKS}
    baseline_mib = memory_used_mib()
    row["vram_baseline_mib"] = baseline_mib

    transcript_dir = Path(args.transcripts_dir)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    options = {"language": args.language, "beam_size": args.beam_size, "vad_filter": True}

    with VramSampler() as sampler:
        model, row["load_s"] = load_model(model_name, compute_type)

        started = time.perf_counter()
        transcribe(model, audios["microfono"][: int(WARMUP_S * 16000)], **options)
        row["warmup_s"] = time.perf_counter() - started

        row["tracks"] = {}
        starts: list[float] = []
        for track, audio in audios.items():
            audio_s = len(audio) / 16000
            started = time.perf_counter()
            segments = transcribe(model, audio, **options)
            compute_s = time.perf_counter() - started
            text = "\n".join(f"[{seg.start:7.2f}] {seg.text}" for seg in segments)
            health = text_health(" ".join(seg.text for seg in segments))
            (transcript_dir / f"{model_name}_{compute_type}_{track}.txt").write_text(
                text + "\n", encoding="utf-8"
            )
            row["tracks"][track] = {
                "audio_s": round(audio_s, 2),
                "compute_s": round(compute_s, 3),
                "rtf": round(real_time_factor(compute_s, audio_s), 4),
                "segments": len(segments),
                "words": health.words,
                "letter_ratio": round(health.letter_ratio, 3),
                "looks_broken": health.looks_broken,
            }
            if track == "microfono":
                starts = [seg.start for seg in segments]

        mic = audios["microfono"]
        window_start = pick_window_start(starts, len(mic) / 16000, WINDOW_S)
        window = mic[int(window_start * 16000) : int((window_start + WINDOW_S) * 16000)]
        times: list[float] = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            window_segments = transcribe(model, window, **options)
            times.append(time.perf_counter() - started)
        window_text = " ".join(seg.text for seg in window_segments)
        row["window"] = {
            "start_s": round(window_start, 2),
            "times_s": [round(t, 3) for t in times],
            "median_s": round(median_s(times), 3),
            "looks_broken": text_health(window_text).looks_broken,
        }
    row["vram_peak_mib"] = peak_over_baseline(sampler.samples_mib, baseline_mib)
    return row


def _spawn_combo(args: argparse.Namespace, model_name: str, compute_type: str) -> dict:
    """Lanza un hijo para una combinación y recoge su fila (o el error si murió)."""
    from services.service_whisper import cuda_library_dirs

    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        [*cuda_library_dirs(), env.get("LD_LIBRARY_PATH", "")]
    ).rstrip(os.pathsep)
    result_path = Path(args.transcripts_dir) / f"{model_name}_{compute_type}.json"
    command = [
        sys.executable,
        "-m",
        "bench.bench_motor",
        "--one",
        f"{model_name}:{compute_type}",
        "--result",
        str(result_path),
        "--audio-prefix",
        args.audio_prefix,
        "--transcripts-dir",
        args.transcripts_dir,
        "--language",
        args.language,
        "--beam-size",
        str(args.beam_size),
        "--repeats",
        str(args.repeats),
    ]
    logger.info("Midiendo %s %s", model_name, compute_type)
    try:
        # La salida del hijo va al mismo log que el padre; no se captura (no se llena un búfer).
        process = subprocess.run(command, cwd=ROOT, env=env, timeout=COMBO_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        return {"model": model_name, "compute_type": compute_type, "error": "tiempo agotado"}
    if result_path.is_file():
        row = json.loads(result_path.read_text(encoding="utf-8"))
        result_path.unlink()
        return row
    return {
        "model": model_name,
        "compute_type": compute_type,
        "error": f"el proceso terminó con código {process.returncode}",
    }


def _child_main(args: argparse.Namespace) -> None:
    model_name, _, compute_type = args.one.partition(":")
    try:
        row = _run_combo(args, model_name, compute_type)
    except Exception as exc:  # toda falla del motor se registra como dato
        logger.exception("Falló %s %s", model_name, compute_type)
        row = {"model": model_name, "compute_type": compute_type, "error": f"{exc}"}
    Path(args.result).write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")


def _parent_main(args: argparse.Namespace) -> None:
    from services.service_gpu import gpu_identity
    from services.service_whisper import engine_versions

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    args.transcripts_dir = str(TRANSCRIPTS_DIR / "bench" / stamp)
    Path(args.transcripts_dir).mkdir(parents=True, exist_ok=True)
    rows = [
        _spawn_combo(args, model_name, compute_type)
        for model_name in args.models
        for compute_type in args.compute_types
    ]
    report = {
        "fecha": stamp,
        "equipo": gpu_identity(),
        "versiones": engine_versions(),
        "audio": {track: Path(f"{args.audio_prefix}_{track}.wav").name for track in TRACKS},
        "opciones": {
            "language": args.language,
            "beam_size": args.beam_size,
            "vad_filter": True,
            "ventana_s": WINDOW_S,
            "repeticiones_ventana": args.repeats,
        },
        "filas": rows,
    }
    BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = BENCH_RESULTS_DIR / f"{stamp}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    table = format_table(rows)
    json_path.with_suffix(".md").write_text(table + "\n", encoding="utf-8")
    logger.info("Resultados en %s\n%s", json_path.relative_to(ROOT), table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Banco del motor de IvyBells")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--compute-types", nargs="+", default=DEFAULT_COMPUTE_TYPES)
    parser.add_argument("--audio-prefix", default=str(RECORDINGS_DIR / "f11b"))
    parser.add_argument("--language", default="es")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=5, help="repeticiones de la ventana de 5 s")
    # Uso interno: el padre lanza un hijo por combinación.
    parser.add_argument("--one", help=argparse.SUPPRESS)
    parser.add_argument("--result", help=argparse.SUPPRESS)
    parser.add_argument("--transcripts-dir", help=argparse.SUPPRESS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    if args.one:
        _child_main(args)
    else:
        _parent_main(args)


if __name__ == "__main__":
    main()
