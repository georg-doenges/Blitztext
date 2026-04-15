"""
AudioRecorder – nimmt Mikrofon-Audio auf und gibt es als NumPy-Float32-Array zurück.
Nutzt sounddevice mit 16 kHz / Mono (das Format, das Whisper erwartet).
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "float32"
BLOCKSIZE = 1024  # Frames pro Callback-Aufruf


class AudioRecorder:
    def __init__(self) -> None:
        self._buffer: deque[np.ndarray] = deque()
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Öffnet den Mikrofon-Stream und beginnt die Aufnahme."""
        with self._lock:
            self._buffer.clear()

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCKSIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stoppt den Stream und gibt das aufgenommene Audio als 1-D float32-Array zurück."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._buffer:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(list(self._buffer), axis=0)

        # Mono: (N, 1) → (N,)
        if audio.ndim == 2:
            audio = audio[:, 0]
        return audio

    @property
    def duration_seconds(self) -> float:
        """Ungefähre Aufnahmedauer in Sekunden (für Mindestlängen-Check)."""
        with self._lock:
            total_frames = sum(chunk.shape[0] for chunk in self._buffer)
        return total_frames / SAMPLE_RATE

    # ------------------------------------------------------------------
    # Interner Callback (läuft auf PortAudio-Thread)
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        # Kopie anlegen, damit der PortAudio-Buffer wiederverwendet werden kann
        with self._lock:
            self._buffer.append(indata.copy())
