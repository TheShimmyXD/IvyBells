# Changelog

Todos los cambios relevantes de IvyBells se registran aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones
[SemVer](https://semver.org/lang/es/): MAYOR.MENOR.PARCHE.

## [Sin publicar]

## [0.2.1] - 2026-11-20

Limpieza y repositorio listo para otra máquina: copia de `jacck_common` en `vendor/`,
instalación más liviana, CI en cada push y la ventana con letras e iconos de 61 KB.

### Agregado
- Captura de la ventana en el README (demo de la interfaz, tema claro y oscuro).
- CI en GitHub Actions: ruff, pytest y Vitest en cada push, sin GPU ni audio.
- Prueba de versión única: falla si `pyproject.toml`, `web/package.json` y su lock,
  `tauri.conf.json`, `Cargo.toml` o `Cargo.lock` no coinciden.

### Cambiado
- La API local y el crate de Tauri de `jacck_common` van copiados en `vendor/jacck_common/`,
  con `vendor/sync_jacck_common.py` y una prueba que falla si la copia se aparta: IvyBells se
  instala en otra máquina sin `../jacck_common`. `.cargo/config.toml` pasa a ser local.
- Instalación más liviana: `install.sh` deja la ventana (12 MB) en `desktop/bin/` y borra
  `desktop/src-tauri/target/` y `web/node_modules/`; un clon limpio pasa de ~4,1 GB a 2,7 GB.
- Vitest sin aislar cada archivo: de 3,3 s a 1,6 s.
- Limpieza: sin `noqa` que no silencian nada (`RUF100`), sin ajustes locales ni perfil viejo
  sin uso, ayudantes de hilos en `app/background.py`, modelo y precisión por defecto en
  `domain/transcription/engine.py`, sin copias en `web/src` y `settings_router` partido en
  Claude y cuenta, perfiles y contextos.
- La demo de la interfaz muestra en el pie la latencia medida en uso real.
- Letras e iconos más livianos: IBM Plex recortado a latín en WOFF2 (como «IvyBells Sans» y
  «IvyBells Mono», por el nombre reservado de la OFL) y Phosphor con solo sus 39 iconos, con
  `resources/build_web_fonts.py` para regenerarlos. Las fuentes de `web/dist` pasan de 723 KB a
  61 KB y `web/dist` de 1,22 MB a 0,55 MB.

### Corregido
- `web/` declara `@types/node`: en un `npm ci` limpio `tsc` no encontraba `node:url`.
- La prueba de provisionales del streaming usa un reloj falso: ya no falla con la máquina
  cargada.

## [0.2.0] - 2026-11-20

La ventana pasa a ser web (Tauri, React y TypeScript) sobre el mismo Python, y la de Qt se
retira. Medido en uso real (125 frases de «Ellos»): latencia mediana 1,5 s, p90 2,4 s.

### Agregado
- Ventana de Tauri con tres módulos (En vivo, con el Agente dentro, y Configuración), temas
  claro y oscuro, y la barra lateral que se pliega al salir el ratón.
- API local (`main.py --api`) con canales SSE para la escucha, el Agente y el chat; la abre y
  la cierra la ventana.
- En vivo: burbujas por hablante, selector de equipo de «Ellos» y «Tú» en la cabecera de cada
  canal, menú del modelo de transcripción, «Seguir en vivo» flotante, marca «Reanudada HH:MM»
  y Guardar `.md` con el diálogo nativo.
- Agente: marcar con clic izquierdo y derecho, Esc y Cancelar, interruptor Anticipado, barra
  de contexto con su desglose y pestaña Chat con respuestas en Markdown.
- Configuración: pestañas Claude (cuenta, modelo, esfuerzo, respaldo y tiempo), Perfil del
  agente (editor con guardado automático) y Contexto (peso por archivo, abrir la carpeta).
- `main.py --install-launcher` deja IvyBells en el menú de aplicaciones con su logo;
  `install.sh` instala `jacck_common` y compila la ventana si encuentra npm y cargo.
- Al detener la escucha, el `.md` termina con la latencia de cada canal (mediana, p90 y
  cuántas frases se midieron), y la misma línea queda en el log.
- Logo de IvyBells (campana dentro del sello ocre de vid2aud y Molink) en el README, en
  versión clara y oscura.

### Cambiado
- `main.py` y el acceso del menú abren la ventana de Tauri (binario de release, sin Vite).
- El código se ordena por conceptos (`domain/`, `services/`, `app/`, `entrypoints/`): la
  escucha, el Agente, el chat, los perfiles y la configuración ya no dependen de Qt.
- Los colores de la interfaz se editan en `web/src/shared/theme/tokens.css`.

### Quitado
- La ventana de Qt (PySide6), `main.py --qt`, `captura_ui.py` y sus pruebas. El entorno pesa
  unos 670 MB menos.

### Corregido
- Un solo `.md` por apertura de la app, y Guardar funciona con la escucha corriendo.
- La app no arrancaba fuera de su carpeta (`python /ruta/main.py`): el relanzamiento con
  cuBLAS y cuDNN no encontraba `main`.
- Una respuesta larga del chat ya no estira el panel del Agente fuera de la ventana.

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
