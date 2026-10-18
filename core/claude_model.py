"""
Configuración del modelo de Claude Code que usa IvyBells.

No hay clave de API: todo pasa por la CLI `claude -p` del autor, con su sesión iniciada.
Este módulo solo describe y valida qué modelo pedir y con qué opciones; quien lance el
proceso toma los argumentos de `ClaudeModelConfig.cli_args()`.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

# Sin herramientas, sin skills, plugins ni MCP del autor y sin guardar la sesión: el
# texto que se envía lo dijo un tercero y puede traer instrucciones.
ISOLATION_ARGS = (
    "--tools",
    "",
    "--strict-mcp-config",
    "--setting-sources",
    "",
    "--no-session-persistence",
)
# Con -p, stream-json exige --verbose.
STREAM_ARGS = ("--output-format", "stream-json", "--include-partial-messages", "--verbose")
JSON_ARGS = ("--output-format", "json")

# Alias que la CLI resuelve al modelo más reciente de cada familia.
MODEL_ALIASES = ("fable", "opus", "sonnet", "haiku")
# Niveles de --effort que acepta la CLI; "" deja el de la sesión por defecto.
EFFORT_LEVELS = ("", "low", "medium", "high", "xhigh", "max")
# Nombre completo de un modelo, por ejemplo claude-sonnet-5-5.
_FULL_NAME = re.compile(r"^claude-[a-z0-9]+(-[a-z0-9]+)*$")

DEFAULT_TIMEOUT_S = 120


def is_valid_model(name: str) -> bool:
    """True si `name` es un alias conocido o un nombre completo con forma claude-..."""
    return name in MODEL_ALIASES or bool(_FULL_NAME.match(name))


def _clean_model(value: object, default: str) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return text if is_valid_model(text) else default


@dataclass(frozen=True, slots=True)
class ClaudeModelConfig:
    """
    Modelo y opciones para llamar a `claude -p`.

    Campos
    ------
    model          : alias (fable, opus, sonnet, haiku) o nombre completo del modelo.
    effort         : nivel de razonamiento; "" no pasa --effort.
    fallback_model : modelo de respaldo si el principal está saturado; "" no pasa ninguno.
    timeout_s      : segundos máximos que se espera la respuesta de la CLI.
    executable     : comando de la CLI (por si no está en el PATH).

    Los valores inválidos leídos del JSON toman su valor por defecto.
    """

    model: str = "sonnet"
    effort: str = ""
    fallback_model: str = ""
    timeout_s: int = DEFAULT_TIMEOUT_S
    executable: str = "claude"

    @classmethod
    def from_dict(cls, data: object) -> ClaudeModelConfig:
        if not isinstance(data, dict):
            return cls()
        base = cls()
        effort = str(data.get("effort") or "").strip().lower()
        fallback = _clean_model(data.get("fallback_model"), "")
        timeout = data.get("timeout_s")
        executable = str(data.get("executable") or "").strip()
        return cls(
            model=_clean_model(data.get("model"), base.model),
            effort=effort if effort in EFFORT_LEVELS else base.effort,
            fallback_model=fallback,
            timeout_s=timeout if isinstance(timeout, int) and timeout > 0 else base.timeout_s,
            executable=executable or base.executable,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def cli_args(self) -> list[str]:
        """Opciones de modelo para la CLI (sin `-p` ni el prompt)."""
        args = ["--model", self.model]
        if self.effort:
            args += ["--effort", self.effort]
        if self.fallback_model and self.fallback_model != self.model:
            args += ["--fallback-model", self.fallback_model]
        return args

    def command(self, system_prompt_file: Path, stream: bool = True) -> list[str]:
        """
        Orden completa de `claude -p` aislada, con el perfil como system prompt.

        El prompt va por stdin y el proceso se lanza en una carpeta vacía, para que la
        CLI no descubra el CLAUDE.md ni las skills del proyecto.
        """
        output = STREAM_ARGS if stream else JSON_ARGS
        return [
            self.executable,
            "-p",
            *self.cli_args(),
            "--system-prompt-file",
            str(system_prompt_file),
            *ISOLATION_ARGS,
            *output,
        ]
