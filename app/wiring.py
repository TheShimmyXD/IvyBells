"""
Raíz de composición: arma los casos de uso con sus servicios.

Las puertas (la consola y la API) piden aquí un caso de uso ya armado y
nunca crean un servicio por su cuenta.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from app.context import ContextLibrary
from app.live import LiveListening
from app.profiles import ProfileLibrary
from app.settings import ClaudeOptions
from domain.claude.claude_model import ClaudeModelConfig
from domain.transcription.engine import EventCallback, TranscriptionEngine
from paths import TRANSCRIPTS_DIR
from services.service_profiles import ProfileStore

Remember = Callable[[str, object], object]


def _whisper_engine(on_event: EventCallback, model: str, compute_type: str) -> TranscriptionEngine:
    # Import diferido: faster-whisper y CUDA solo se cargan al iniciar una escucha.
    from services.service_streaming import create_whisper_engine

    return create_whisper_engine(on_event, model, compute_type)


def build_live(
    closed_sources: Iterable[str] = (), transcripts_dir: Path = TRANSCRIPTS_DIR
) -> LiveListening:
    """La escucha en vivo con Whisper en la GPU y la captura de PipeWire."""
    return LiveListening(_whisper_engine, transcripts_dir, closed_sources)


def build_claude_options(
    config: ClaudeModelConfig, profile: str, context: str, remember: Remember
) -> ClaudeOptions:
    """
    La configuración de Claude con los perfiles y el contexto recordados.

    `remember(clave, valor)` guarda cada elección en `app_settings.json`.
    """
    store = ProfileStore()
    return ClaudeOptions(
        config,
        lambda claude: remember("claude", claude),
        profiles=ProfileLibrary(store, profile, lambda name: remember("agent_profile", name)),
        context=ContextLibrary(context, lambda name: remember("agent_context", name)),
    )
