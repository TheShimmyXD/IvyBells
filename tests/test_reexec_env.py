"""Entorno del relanzamiento con CUDA: librerías y raíz del proyecto, sin perder lo previo."""

from __future__ import annotations

import os

from paths import ROOT
from services.service_whisper import reexec_env


def test_reexec_env_adds_libraries_and_project_root(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/previa")
    monkeypatch.setenv("PYTHONPATH", "/otra")
    env = reexec_env(["/cublas", "/cudnn"])
    assert env["LD_LIBRARY_PATH"].split(os.pathsep) == ["/cublas", "/cudnn", "/previa"]
    assert env["PYTHONPATH"].split(os.pathsep) == [str(ROOT), "/otra"]


def test_reexec_env_without_previous_values(monkeypatch):
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    env = reexec_env(["/cublas"])
    assert env["LD_LIBRARY_PATH"] == "/cublas"
    assert env["PYTHONPATH"] == str(ROOT)
