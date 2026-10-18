# Muestra de `claude -p`

- CLI: 2.1.302 (Claude Code)
- Fecha: 2026-10-17
- Generada con `python -m bench.bench_claude --fixture`, con el perfil y la frase
  de ejemplo de `bench/bench_claude.py` (nada de una conversación real).
- Limpia: sin ids de sesión, rutas, firmas ni el evento de límites de la cuenta.
- Si cambia la versión de la CLI, se regenera antes de tocar el lector.

## `auth status --json`

- `auth_status.json`: sesión iniciada (plan pro), con el correo, la organización y las
  rutas reemplazados. `auth_status_sin_sesion.json`: carpeta `CLAUDE_CONFIG_DIR` vacía
  (la CLI sale con código 1). Misma CLI y fecha que arriba.
