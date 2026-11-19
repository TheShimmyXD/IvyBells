"""
Raíz de composición: arma los casos de uso con sus servicios.

Las puertas (la ventana Qt, la consola y la API) piden aquí un caso de uso ya armado y
nunca crean un servicio por su cuenta.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.live import LiveListening
from domain.transcription.engine import EventCallback, TranscriptionEngine
from paths import TRANSCRIPTS_DIR


def _whisper_engine(on_event: EventCallback, model: str, compute_type: str) -> TranscriptionEngine:
    # Import diferido: faster-whisper y CUDA solo se cargan al iniciar una escucha.
    from services.service_streaming import create_whisper_engine

    return create_whisper_engine(on_event, model, compute_type)


def build_live(
    closed_sources: Iterable[str] = (), transcripts_dir: Path = TRANSCRIPTS_DIR
) -> LiveListening:
    """La escucha en vivo con Whisper en la GPU y la captura de PipeWire."""
    return LiveListening(_whisper_engine, transcripts_dir, closed_sources)
