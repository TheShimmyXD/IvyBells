from __future__ import annotations

import wave

import numpy as np
import pytest

from services.service_whisper import load_audio


def _write_wav(path, samples, rate=16000, channels=1):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.astype(np.int16).tobytes())


def test_load_audio_returns_float32_in_unit_range(tmp_path):
    samples = (np.sin(np.linspace(0, 100, 16000)) * 16384).astype(np.int16)
    path = tmp_path / "tono.wav"
    _write_wav(path, samples)
    audio = load_audio(path)
    assert audio.dtype == np.float32
    assert len(audio) == 16000
    assert np.abs(audio).max() == pytest.approx(0.5, abs=1e-3)


def test_load_audio_rejects_other_rates(tmp_path):
    path = tmp_path / "44k.wav"
    _write_wav(path, np.zeros(441, dtype=np.int16), rate=44100)
    with pytest.raises(ValueError):
        load_audio(path)
