"""Al morir la ventana de Tauri no queda ningun Python.

Abre una ventana real por unos segundos, asi que solo corre a pedido:

    IVYBELLS_DESKTOP_TEST=1 .venv/bin/python -m pytest -q tests/test_desktop_close.py

Mata la ventana con SIGKILL (el peor caso: no alcanza a apagar nada) y espera a que la API
salga sola al cerrarse su entrada estandar (jacck_tauri y jacck_common.webapi). Antes hay que
compilar la ventana una vez (``cd web && npm run tauri dev`` o ``cargo build`` en
``desktop/src-tauri``).
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from services.service_desktop import release_binary

ROOT = Path(__file__).resolve().parents[1]
# El de desarrollo, al lado del de release (carpeta compartida o la propia).
_RELEASE = release_binary(ROOT / "desktop" / "src-tauri")
BINARY = _RELEASE.parent.parent / "debug" / _RELEASE.name
API_MARK = "--api"
START_TIMEOUT_S = 30.0
EXIT_TIMEOUT_S = 5.0

pytestmark = pytest.mark.skipif(
    os.environ.get("IVYBELLS_DESKTOP_TEST") != "1" or not BINARY.exists(),
    reason="abre una ventana real: IVYBELLS_DESKTOP_TEST=1 y la ventana compilada",
)


def api_children(parent: int) -> list[int]:
    """PIDs de los hijos de ``parent`` que corren la API (lee /proc, sin psutil)."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        ppid = int(stat.rsplit(")", 1)[1].split()[1])
        if ppid == parent and API_MARK in cmdline:
            found.append(int(entry.name))
    return found


def alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def wait_until(check, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return False


def test_killing_the_window_leaves_no_python() -> None:
    env = {**os.environ, "GDK_BACKEND": "x11"}
    window = subprocess.Popen(
        [str(BINARY)],
        cwd=BINARY.parent,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        assert wait_until(lambda: api_children(window.pid), START_TIMEOUT_S), "la API no arranco"
        (api,) = api_children(window.pid)
        # La API ya anuncio su puerto y vigila la entrada estandar.
        time.sleep(2.0)
        started = time.monotonic()
        window.send_signal(signal.SIGKILL)
        window.wait(timeout=EXIT_TIMEOUT_S)
        assert wait_until(lambda: not alive(api), EXIT_TIMEOUT_S), "la API quedo viva"
        print(f"API fuera {time.monotonic() - started:.2f} s despues de matar la ventana")
    finally:
        if window.poll() is None:
            os.killpg(window.pid, signal.SIGKILL)
