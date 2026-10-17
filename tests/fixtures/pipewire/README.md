# Muestras de PipeWire

Salida real de `pactl` en la máquina de desarrollo, capturada el 2026-10-17 con
`LC_ALL=C pactl info` y `LC_ALL=C pactl list short sources`.

- `pactl` 16.1; servidor «PulseAudio (on PipeWire 1.0.5)», protocolo 35.
- Enmascarados: nombre de usuario, nombre del equipo y cookie. Todo lo demás es tal cual.

| Archivos | Situación |
|---|---|
| `pactl_info.txt`, `pactl_list_short_sources.txt` | Solo la tarjeta de la placa; la entrada predeterminada era la propia `.monitor`. |
| `pactl_info_headset_usb.txt`, `pactl_list_short_sources_headset_usb.txt` | Headset USB conectado y en uso por el navegador (Meet): salida y entrada predeterminadas son las del headset. |

Si cambia la versión de PipeWire o de `pactl`, se regeneran las muestras antes de corregir el código.
