"""
Transcriber – lädt das Whisper-Modell asynchron und transkribiert Audio-Arrays.
Das Modell wird in einem Background-Thread geladen, damit der Tray sofort erscheint.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np

MIN_DURATION_SECONDS = 0.3  # Kürzere Aufnahmen werden verworfen

_TIMEOUT_SECONDS = 90  # Watchdog: so lange darf das Laden maximal dauern

_TIMEOUT_MESSAGE = (
    "Whisper konnte nicht geladen werden.\n\n"
    "Mögliche Ursache: Die installierte PyTorch-Version ist nicht kompatibel "
    "(z. B. CUDA-Build auf älterer Grafikkarte).\n\n"
    "Lösung – diesen Befehl im Blitztext-Ordner ausführen:\n\n"
    "  .venv\\Scripts\\pip install torch\n"
    "      --index-url https://download.pytorch.org/whl/cpu\n"
    "      --force-reinstall\n\n"
    "Danach Blitztext neu starten."
)


class Transcriber:
    def __init__(self, model_name: str = "small", whisper_device: str = "auto") -> None:
        self._model_name = model_name
        self._whisper_device = whisper_device  # "auto" | "cpu" | "cuda"
        self._model = None
        self._device = "cpu"
        self._ready = threading.Event()
        self._on_ready_callback: Optional[Callable[[], None]] = None
        self._on_error_callback: Optional[Callable[[str], None]] = None

        # Watchdog: löst aus, wenn das Laden zu lange dauert
        self._watchdog = threading.Timer(_TIMEOUT_SECONDS, self._loading_timeout)
        self._watchdog.daemon = True
        self._watchdog.start()

        # Modell im Hintergrund laden
        t = threading.Thread(target=self._load_model, daemon=True, name="WhisperLoader")
        t.start()

    def set_on_ready(self, callback: Callable[[], None]) -> None:
        """Wird aufgerufen, sobald das Modell geladen ist."""
        self._on_ready_callback = callback
        # Wenn bereits bereit, sofort auslösen
        if self._ready.is_set():
            callback()

    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """Wird aufgerufen, wenn das Laden fehlschlägt oder zu lange dauert."""
        self._on_error_callback = callback

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

    def _loading_timeout(self) -> None:
        """Wird vom Watchdog ausgelöst, wenn das Laden zu lange dauert."""
        if self._ready.is_set():
            return
        import logging
        logging.getLogger(__name__).error(
            "Whisper-Loader Timeout nach %d Sekunden – wahrscheinlich hängt import torch",
            _TIMEOUT_SECONDS,
        )
        if self._on_error_callback:
            self._on_error_callback(_TIMEOUT_MESSAGE)

    def _load_model(self) -> None:
        import logging
        import torch
        import whisper  # Import hier, damit startup schnell bleibt

        log = logging.getLogger(__name__)
        log.info("Whisper-Loader gestartet (Modell: %s, device-setting: %s)",
                 self._model_name, self._whisper_device)

        # Gerät bestimmen
        if self._whisper_device == "cpu":
            use_cuda = False
            log.info("CPU-Modus erzwungen (whisper_device=cpu)")
        elif self._whisper_device == "cuda":
            use_cuda = True
            log.info("CUDA-Modus erzwungen (whisper_device=cuda)")
        else:
            use_cuda = torch.cuda.is_available()
            log.info("Auto-Erkennung: torch.cuda.is_available() = %s", use_cuda)
            if use_cuda:
                log.info("CUDA-Gerät: %s", torch.cuda.get_device_name(0))

        if use_cuda:
            try:
                self._device = "cuda"
                log.info("Lade Whisper auf CUDA ...")
                self._model = whisper.load_model(self._model_name, device="cuda")
                log.info("Whisper geladen auf CUDA")
            except Exception as e:
                log.warning("CUDA-Loading fehlgeschlagen (%s) – falle auf CPU zurück", e)
                self._device = "cpu"
                log.info("Lade Whisper auf CPU (Fallback) ...")
                self._model = whisper.load_model(self._model_name, device="cpu")
                log.info("Whisper geladen auf CPU (Fallback)")
        else:
            self._device = "cpu"
            log.info("Lade Whisper auf CPU ...")
            self._model = whisper.load_model(self._model_name, device="cpu")
            log.info("Whisper geladen auf CPU")

        self._watchdog.cancel()
        self._ready.set()
        if self._on_ready_callback:
            self._on_ready_callback()
