# IvyBells

Transcribe en vivo, en la GPU de tu equipo y sin mandar el audio a ninguna nube,
lo que suena por los parlantes o audífonos y lo que dices por el micrófono, con
**«Ellos»** y **«Tú»** separados. Sirve para llamadas de Meet, Teams o cualquier
otra app: escucha la salida de audio del sistema, no la app.

La ventana tiene tres módulos sobre la misma escucha:

- **Transcripción:** las dos columnas en vivo, con frases provisionales que se
  confirman al terminar cada frase. Un clic en el icono de un canal lo cierra o
  lo abre.
- **Agente:** mientras transcribe, Claude Code propone qué responder según un
  perfil (quién eres y qué buscas en la llamada) y el contexto de tu empresa
  (PDF, Word o Markdown). En modo **Anticipado** responde en cuanto la otra
  persona termina de hablar. **Chat** abre una conversación tuya con Claude que
  ve las dos columnas, con su propio modelo y esfuerzo.
- **Configuración:** cuenta de Claude, modelo y esfuerzo, perfiles y contextos
  guardados, y una barra con cuánto ocupa cada parte del contexto.

## Cifras medidas

En una GTX 1660 Super (6 GB), con `large-v3-turbo` en `int8`, banco del
2026-10-17 en `bench/resultados/`:

| Medida | Valor |
|---|---|
| Velocidad (RTF, menor es mejor) | 0,044: 60 s de audio en 2,6 s |
| VRAM del motor | 1340 MiB |
| Carga del modelo | 2,9 s |

## Qué no toca

- El audio no sale del equipo: la transcripción corre en tu GPU con
  faster-whisper. Solo el módulo Agente manda **texto** (la transcripción, el
  perfil y el contexto) a Claude, con tu propia sesión de Claude Code.
- No cambia la salida ni la entrada predeterminadas del sistema y no toca la
  configuración de PipeWire: solo lee las fuentes con `pactl` y `parec`.
- No usa `sudo` ni instala CUDA Toolkit: cuBLAS y cuDNN llegan por `pip` dentro
  de `.venv/`.
- Lo suyo queda en esta carpeta (`resources/json/`, `logs/`,
  `transcripciones/`), la sesión de Claude de cada cuenta en
  `~/.local/share/ivybells/` y el modelo de Whisper en `~/.cache/huggingface/`.
  Tus perfiles y contextos no se versionan.

## Requisitos

- Linux con PipeWire (probado en Ubuntu 26.04 con PipeWire 1.6.2) y
  `pactl`/`parec` (paquete `pulseaudio-utils`).
- Una GPU NVIDIA con su driver.
- Python 3.13 o superior con `venv` (en Debian/Ubuntu/Mint: `python3-venv`).
- Para el módulo Agente, la CLI de [Claude Code](https://claude.com/claude-code)
  con una sesión iniciada. La transcripción funciona sin ella.

## Instalación

```bash
git clone https://github.com/TheShimmyXD/IvyBells.git
cd IvyBells
./install.sh
```

`install.sh` crea `.venv/` dentro de la carpeta, instala las dependencias y
deja IvyBells en el menú de aplicaciones. La primera vez que transcribe
descarga el modelo (1,6 GB).

Para abrirlo sin el menú:

```bash
.venv/bin/python main.py
```

## Primer uso

1. Mira que IvyBells vea tus fuentes de audio:
   ```bash
   .venv/bin/python main.py --fuentes
   ```
   Debe salir una fuente `.monitor` (lo que suena) y tu micrófono.
2. Abre la ventana, elige el modelo y pulsa **Iniciar**. «Ellos» es lo que
   suena por los parlantes; «Tú», el micrófono.
3. Para el Agente, en **Configuración** elige la cuenta de Claude, crea un
   perfil (hay uno de ejemplo en `resources/agent/perfiles/ejemplo.md`) y
   agrega las rutas del contexto de tu empresa.

En una llamada real, avisa a los demás participantes de que la estás
transcribiendo.

### En la consola

```bash
.venv/bin/python main.py --cli                 # large-v3-turbo int8
.venv/bin/python main.py --cli --model small   # otro modelo de faster-whisper
```

La transcripción queda en `transcripciones/` como `.md`.

## Pruebas

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Las pruebas usan audio sintético y muestras reales de `pactl` en
`tests/fixtures/pipewire/`; no necesitan GPU ni micrófono.

## Licencia

MIT. Las letras IBM Plex van con su licencia OFL (`resources/fonts/OFL.txt`) y
los iconos Phosphor con la suya (`resources/icons/LICENSE.txt`).
