"""
Motor en vivo: VAD por fuente, re-transcripción de la frase en curso y LocalAgreement.

Un solo reconocedor (un modelo en la GPU) atiende a todas las fuentes; las llamadas se
serializan porque `feed` corre en el hilo de quien lo llame.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable

import numpy as np

from core.engine import EventCallback, TranscriptEvent
from core.local_agreement import LocalAgreement
from core.phrase_segmenter import PhraseEventKind, PhraseSegmenter
from services.service_vad import VAD_WINDOW_SAMPLES

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Silencio que cierra una frase, cada cuánto se re-transcribe y tope de una frase.
MIN_SILENCE_S = 0.5
PARTIAL_INTERVAL_S = 1.0
MAX_PHRASE_S = 20.0
# Audio previo al disparo del VAD que se agrega al inicio de la frase (no cortar la sílaba).
PRE_SPEECH_S = 0.2
# Frases más cortas que esto no se transcriben: suelen ser ruidos y Whisper inventa texto.
MIN_PHRASE_S = 0.3
# Con más atraso que esto respecto al tiempo real se saltan los provisionales (los finales
# siempre corren): cada llamada al modelo cuesta un tiempo casi fijo y dos fuentes no caben.
# Además, tras cada llamada el modelo queda libre al menos lo que ella duró: los provisionales
# usan a lo sumo la mitad del cómputo y un final rara vez espera detrás de uno.
MAX_LAG_FOR_PARTIAL_S = 0.3

Recognizer = Callable[[np.ndarray], str]
VadFn = Callable[[np.ndarray], list[float]]


def _windows(seconds: float) -> int:
    return max(1, round(seconds * SAMPLE_RATE / VAD_WINDOW_SAMPLES))


class _SourceStream:
    """Estado de una fuente: resto sin ventana completa, frase en curso y su acuerdo."""

    def __init__(self) -> None:
        self.segmenter = PhraseSegmenter(
            min_silence_windows=_windows(MIN_SILENCE_S),
            max_phrase_windows=_windows(MAX_PHRASE_S),
        )
        self.agreement = LocalAgreement()
        self.remainder = np.zeros(0, dtype=np.float32)
        self.recent: deque[np.ndarray] = deque(maxlen=_windows(PRE_SPEECH_S))
        self.phrase: list[np.ndarray] = []
        self.phrase_start_window = 0
        self.windows_since_partial = 0
        self.speech_windows = 0
        self.received_samples = 0


class StreamingEngine:
    """Implementa `TranscriptionEngine` con un reconocedor y un VAD inyectados."""

    def __init__(
        self,
        on_event: EventCallback,
        recognizer: Recognizer | None = None,
        vad: VadFn | None = None,
        load: Callable[[], tuple[Recognizer, VadFn]] | None = None,
        clock: Callable[[], float] = time.perf_counter,
        partial_interval_s: float = PARTIAL_INTERVAL_S,
    ) -> None:
        self._on_event = on_event
        self._partial_windows = _windows(partial_interval_s)
        self._recognizer = recognizer
        self._vad = vad
        self._load = load
        self._clock = clock
        self._first_feed_at: float | None = None
        self._last_call_end = float("-inf")
        self._last_call_cost = 0.0
        self._streams: dict[str, _SourceStream] = {}

    def start(self) -> None:
        if self._load is not None and self._recognizer is None:
            self._recognizer, self._vad = self._load()

    def feed(self, source: str, samples: np.ndarray) -> None:
        stream = self._streams.setdefault(source, _SourceStream())
        if self._first_feed_at is None:
            # El primer bloque llega cuando ya terminó de sonar.
            self._first_feed_at = self._clock() - len(samples) / SAMPLE_RATE
        stream.received_samples += len(samples)
        audio = np.concatenate([stream.remainder, samples.astype(np.float32, copy=False)])
        usable = len(audio) - len(audio) % VAD_WINDOW_SAMPLES
        stream.remainder = audio[usable:]
        windows = audio[:usable].reshape(-1, VAD_WINDOW_SAMPLES)
        probs = self._vad(audio[:usable]) if usable else []

        for window, prob in zip(windows, probs, strict=True):
            forced = False
            for event in stream.segmenter.push(prob):
                if event.kind is PhraseEventKind.END:
                    forced = event.forced
                    self._finish_phrase(source, stream, event.window)
                    continue
                # Tras un corte forzado no se repite el audio previo: ya está en la frase anterior.
                stream.phrase = [] if forced else list(stream.recent)
                stream.phrase_start_window = event.window - len(stream.phrase)
                stream.windows_since_partial = 0
                stream.speech_windows = 0
            if stream.segmenter.in_speech:
                stream.phrase.append(window)
                stream.windows_since_partial += 1
                stream.speech_windows += prob >= stream.segmenter.threshold
            stream.recent.append(window)

        if (
            stream.segmenter.in_speech
            and stream.windows_since_partial >= self._partial_windows
            and self.lag_s(source) <= MAX_LAG_FOR_PARTIAL_S
            and self._clock() - self._last_call_end >= self._last_call_cost
        ):
            self._emit_partial(source, stream)

    def lag_s(self, source: str) -> float:
        """Cuánto va atrasado el motor con esa fuente: tiempo de pared menos audio recibido."""
        stream = self._streams.get(source)
        if stream is None or self._first_feed_at is None:
            return 0.0
        return self._clock() - self._first_feed_at - stream.received_samples / SAMPLE_RATE

    def end_source(self, source: str) -> None:
        stream = self._streams.get(source)
        if stream is None or not stream.segmenter.in_speech:
            return
        end_window = stream.phrase_start_window + len(stream.phrase)
        # El resto que no completa una ventana del VAD también es parte de la frase.
        stream.phrase.append(stream.remainder)
        self._finish_phrase(source, stream, end_window)
        stream.segmenter.in_speech = False

    def skip(self, source: str, num_samples: int) -> None:
        """
        Cuenta como recibido el audio de un canal cerrado sin pasarlo por el VAD ni el modelo:
        los tiempos de las frases siguientes y el atraso siguen al reloj de pared.
        """
        if num_samples <= 0:
            return
        if self._first_feed_at is None:
            self._first_feed_at = self._clock() - num_samples / SAMPLE_RATE
        self.end_source(source)
        stream = self._streams.setdefault(source, _SourceStream())
        stream.received_samples += num_samples
        pending = len(stream.remainder) + num_samples
        stream.segmenter.skip(pending // VAD_WINDOW_SAMPLES)
        # Lo que no completa una ventana se rellena con silencio para no correr los tiempos.
        stream.remainder = np.zeros(pending % VAD_WINDOW_SAMPLES, dtype=np.float32)
        stream.recent.clear()

    def stop(self) -> None:
        for source in self._streams:
            self.end_source(source)

    def _emit_partial(self, source: str, stream: _SourceStream) -> None:
        stream.windows_since_partial = 0
        words = self._recognize(np.concatenate(stream.phrase)).split()
        _committed, provisional = stream.agreement.update(words)
        stable = len(stream.agreement.committed)
        start_s, end_s = self._span(stream, stream.phrase_start_window + len(stream.phrase))
        self._on_event(
            TranscriptEvent(
                source=source,
                is_final=False,
                text=" ".join(stream.agreement.committed + provisional),
                start_s=start_s,
                end_s=end_s,
                stable_words=stable,
            )
        )

    def _finish_phrase(self, source: str, stream: _SourceStream, end_window: int) -> None:
        phrase = stream.phrase
        stream.phrase = []
        start_s, end_s = self._span(stream, end_window)
        voiced_s = stream.speech_windows * VAD_WINDOW_SAMPLES / SAMPLE_RATE
        if voiced_s < MIN_PHRASE_S or not phrase:
            stream.agreement.finish([])
            return
        words = stream.agreement.finish(self._recognize(np.concatenate(phrase)).split())
        if not words:
            return
        self._on_event(
            TranscriptEvent(
                source=source,
                is_final=True,
                text=" ".join(words),
                start_s=start_s,
                end_s=end_s,
                stable_words=len(words),
            )
        )

    def _recognize(self, audio: np.ndarray) -> str:
        started = self._clock()
        text = self._recognizer(audio)
        self._last_call_end = self._clock()
        self._last_call_cost = self._last_call_end - started
        return text

    @staticmethod
    def _span(stream: _SourceStream, end_window: int) -> tuple[float, float]:
        window_s = VAD_WINDOW_SAMPLES / SAMPLE_RATE
        return max(0, stream.phrase_start_window) * window_s, end_window * window_s


def create_whisper_engine(
    on_event: EventCallback,
    model_name: str = "large-v3-turbo",
    compute_type: str = "int8",
    language: str = "es",
    beam_size: int = 5,
    partial_interval_s: float = PARTIAL_INTERVAL_S,
) -> StreamingEngine:
    """Motor con faster-whisper en la GPU y el VAD Silero; el modelo se carga en `start`."""

    def load() -> tuple[Recognizer, VadFn]:
        from services.service_vad import SileroVad
        from services.service_whisper import load_model, transcribe

        model, load_s = load_model(model_name, compute_type)
        logger.info("Modelo %s %s cargado en %.1f s", model_name, compute_type, load_s)

        def recognize(audio: np.ndarray) -> str:
            segments = transcribe(
                model, audio, language=language, beam_size=beam_size, vad_filter=False
            )
            return " ".join(segment.text for segment in segments)

        return recognize, SileroVad()

    return StreamingEngine(on_event, load=load, partial_interval_s=partial_interval_s)
