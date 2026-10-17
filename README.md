# IvyBells

Transcripción en tiempo real, local y en GPU, de lo que suena por los parlantes o audífonos
(la fuente `.monitor` de PipeWire) y del micrófono, con «Tú» y «Ellos» separados. Sin nube.

## Requisitos

- Linux con PipeWire y una GPU NVIDIA (la de desarrollo es una GTX 1660 Super).
- Python 3.13 y un `.venv` local.

## Puesta en marcha

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python main.py
```

## Pruebas

```bash
.venv/bin/python -m pytest -q
```

## Glosario

*Vacío por ahora; se llena al introducir términos del dominio.*
