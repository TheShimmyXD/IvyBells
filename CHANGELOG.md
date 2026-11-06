# Changelog

Todos los cambios relevantes de IvyBells se registran aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones
[SemVer](https://semver.org/lang/es/): MAYOR.MENOR.PARCHE.

## [Sin publicar]

### Agregado
- Logo de IvyBells al inicio del README, en versión para tema claro y oscuro; el acceso del
  menú usa la misma campana.

## [0.1.0] - 2026-11-06

Primera versión en GitHub.

### Agregado
- Transcripción en vivo y local en la GPU con faster-whisper (`large-v3-turbo` int8 por
  defecto): lo que suena por los parlantes («Ellos», la fuente `.monitor` de PipeWire) y el
  micrófono («Tú»), con VAD, frases provisionales y confirmación por acuerdo.
- Fuentes leídas con `pactl` según la salida y la entrada predeterminadas, sin cambiarlas;
  aviso único cuando una fuente se sustituye.
- Ventana PySide6 con tres módulos (Transcripción, Agente y Configuración), temas claro y
  oscuro, y modelo, fuentes y módulo recordados entre sesiones.
- Módulo Agente: respuestas de Claude Code (`claude -p` aislado) según un perfil y el
  contexto de la empresa (PDF, Word y Markdown), con modo Anticipado, selección por mensaje
  completo, contextos con nombre y barra de contexto por partes.
- Chat propio en la columna del Agente, con modelo y esfuerzo independientes.
- Modo consola (`main.py --cli`) con la transcripción en `.md`, y `main.py --fuentes`.
- Bancos del motor, en vivo y de Claude, con sus corridas en `bench/resultados/`.
- `install.sh`: entorno virtual, dependencias y acceso en el menú de aplicaciones.
