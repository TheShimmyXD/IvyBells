from __future__ import annotations

import numpy as np

VAD_WINDOW_SAMPLES = 512


class SileroVad:
    """
    Probabilidad de voz por ventana de 512 muestras (32 ms a 16 kHz).

    Usa el Silero v6 que trae faster-whisper (onnxruntime en CPU). Ese modelo no guarda
    estado entre llamadas: se le pasan bloques de ventanas completas.
    """

    def __init__(self) -> None:
        from faster_whisper.vad import get_vad_model

        self._model = get_vad_model()

    def __call__(self, windows: np.ndarray) -> list[float]:
        """Recibe un múltiplo de 512 muestras y devuelve una probabilidad por ventana."""
        if len(windows) == 0:
            return []
        probs = self._model(windows.astype(np.float32, copy=False))
        return [float(prob) for prob in np.asarray(probs).reshape(-1)]
