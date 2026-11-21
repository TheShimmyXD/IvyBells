# Changelog

Todos los cambios relevantes de IvyBells se registran aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones
[SemVer](https://semver.org/lang/es/): MAYOR.MENOR.PARCHE.

## [Sin publicar]

### Cambiado
- La API local y el crate de Tauri de `jacck_common` van copiados en `vendor/jacck_common/`,
  con `vendor/sync_jacck_common.py` y una prueba que falla si la copia se aparta: IvyBells se
  instala en otra máquina sin `../jacck_common`. `.cargo/config.toml` pasa a ser local.

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
