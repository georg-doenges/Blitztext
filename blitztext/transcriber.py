"""
Transcriber – lädt das Whisper-Modell asynchron und transkribiert Audio-Arrays.
Das Modell wird in einem Background-Thread geladen, damit der Tray sofort erscheint.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np

MIN_DURATION_SECONDS = 0.3  # Kürzere Aufnahmen werden verworfen


class Transcriber:
    def __init__(self, model_name: str = "small") -> None:
        self._model_name = model_name
        self._model = None
        self._device = "cpu"
        self._ready = threading.Event()
        self._on_ready_callback: Optional[Callable[[], None]] = None

        # Modell im Hintergrund laden
        t = threading.Thread(target=self._load_model, daemon=True, name="WhisperLoader")
        t.start()

    def set_on_ready(self, callback: Callable[[], None]) -> None:
        """Wird aufgerufen, sobald das Modell geladen ist."""
        self._on_ready_callback = callback
        # Wenn bereits bereit, sofort auslösen
        if self._ready.is_set():
            callback()

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    def transcribe(self, audio: np.ndarray, language: str = "de") -> str:
        """
        Transkribiert ein float32-NumPy-Array (16 kHz, Mono).
        Blockiert, bis das Modell geladen ist.
        Gibt einen leeren String zurück, wenn die Aufnahme zu kurz ist.
        """
        self._ready.wait()

        duration = len(audio) / 16_000
        if duration < MIN_DURATION_SECONDS:
            return ""

        kwargs: dict = {
            "task": "transcribe",
            "fp16": self._device == "cuda",
        }
        if language:
            kwargs["language"] = language

        result = self._model.transcribe(audio, **kwargs)
        return result["text"].strip()

    # ------------------------------------------------------------------
    # Interner Background-Loader
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        import torch
        import whisper  # Import hier, damit startup schnell bleibt

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = whisper.load_model(self._model_name, device=self._device)
        self._ready.set()
        if self._on_ready_callback:
            self._on_ready_callback()
