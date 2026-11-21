"""
Arranque de una API local (de Venona).

1. Token: el que pase quien lanza el proceso en ``<APP>_API_TOKEN`` (la ventana de Tauri)
   o uno nuevo (``session_token``). Quien llama arma su app con el y luego ``serve``.
2. Puerto al azar: el socket se abre en ``127.0.0.1:0`` y uvicorn lo recibe ya abierto
   (sin la carrera de elegir un puerto y abrirlo despues).
3. Sesion: puerto y token van a un JSON (fuera de Git, permisos 0600) para que el Vite de
   desarrollo los lea; se borra al apagar.
4. ``on_ready(port)``: por defecto escribe ``<APP>_API_PORT=<puerto>`` en la salida
   estandar, que es lo que lee la ventana. El token nunca sale por la consola ni por el
   registro; uvicorn corre sin registro de accesos.
5. Con ``<APP>_API_WATCH_STDIN=1`` la API se apaga sola cuando se cierra su entrada
   estandar: la ventana la cierra al salir y el sistema la cierra si la ventana muere de
   golpe, asi no queda ningun Python suelto (ni la VRAM tomada).
6. Al empezar a apagar se terminan los SSE abiertos (``stop_streams``): uvicorn espera a
   cada respuesta en curso y la ventana deja los suyos abiertos al cerrarse. Lo que quede
   pasado ``GRACEFUL_SHUTDOWN_S`` se cancela.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Protocol

import uvicorn
from fastapi import FastAPI

from jacck_common.webapi.names import SidecarNames
from jacck_common.webapi.security import LOCAL_HOST, new_token
from jacck_common.webapi.server import stop_streams

logger = logging.getLogger(__name__)

BACKLOG = 64
# Tope para las respuestas que sigan abiertas al apagar (la ventana mata a los 5 s).
GRACEFUL_SHUTDOWN_S = 2


class _Stoppable(Protocol):
    should_exit: bool


def bind_local_socket() -> socket.socket:
    """Socket TCP en 127.0.0.1 con un puerto libre que elige el sistema, ya escuchando:
    lo que llegue antes de que uvicorn arranque espera en la cola, no se rechaza."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LOCAL_HOST, 0))
    sock.listen(BACKLOG)
    sock.set_inheritable(True)
    return sock


def session_token(names: SidecarNames, environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get(names.token_env, "").strip() or new_token()


def write_session(path: Path, port: int, token: str) -> None:
    """Escribe el archivo de sesion solo para el usuario (0600) desde el primer byte."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"host": LOCAL_HOST, "port": port, "token": token, "pid": os.getpid()})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)


def watch_stdin_requested(names: SidecarNames, environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get(names.watch_stdin_env, "").strip() == "1"


def stop_when_stream_closes(stream: BinaryIO, server: _Stoppable) -> None:
    """Lee ``stream`` hasta el fin (lo que llegue se ignora) y pide a uvicorn que apague."""
    while stream.read(4096):
        pass
    logger.info("Se cerro la entrada estandar: quien lanzo la API ya no esta")
    server.should_exit = True


def announce_port(names: SidecarNames) -> Callable[[int], None]:
    """La linea que lee la ventana; va directo a la salida estandar, no al registro."""

    def announce(port: int) -> None:
        sys.stdout.write(names.port_line(port) + "\n")
        sys.stdout.flush()

    return announce


class _StreamsFirstServer(uvicorn.Server):
    """uvicorn que, antes de esperar las respuestas en curso, termina los SSE de la app."""

    def __init__(self, config: uvicorn.Config, api: FastAPI) -> None:
        super().__init__(config)
        self._api = api

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        stop_streams(self._api)
        await super().shutdown(sockets)


def _exit_on_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(0)


def serve(
    api: FastAPI,
    *,
    names: SidecarNames,
    token: str,
    session_path: Path,
    on_ready: Callable[[int], None] | None = None,
    on_stop: Callable[[], None] | None = None,
) -> int:
    """Corre ``api`` hasta Ctrl+C, SIGTERM o el cierre de la entrada estandar.
    ``on_stop`` libera lo de la app (hilos, GPU) antes de borrar la sesion."""
    sock = bind_local_socket()
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        api,
        log_config=None,
        access_log=False,
        lifespan="off",
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_S,
    )
    server = _StreamsFirstServer(config, api)
    write_session(session_path, port, token)
    logger.info("API local en %s:%d", LOCAL_HOST, port)
    (on_ready or announce_port(names))(port)
    # uvicorn atrapa SIGTERM, apaga y lo vuelve a lanzar con el manejador de antes: con el
    # de fabrica el proceso moria sin borrar la sesion. Este lo vuelve un SystemExit.
    previous = signal.signal(signal.SIGTERM, _exit_on_sigterm)
    if watch_stdin_requested(names):
        threading.Thread(
            target=stop_when_stream_closes,
            args=(sys.stdin.buffer, server),
            name="api-stdin-watch",
            daemon=True,
        ).start()
    try:
        server.run(sockets=[sock])
    except (KeyboardInterrupt, SystemExit) as exc:
        logger.info("Apagado pedido (%s)", type(exc).__name__)
    finally:
        if on_stop is not None:
            on_stop()
        signal.signal(signal.SIGTERM, previous)
        session_path.unlink(missing_ok=True)
        sock.close()
        logger.info("API local apagada")
    return 0
