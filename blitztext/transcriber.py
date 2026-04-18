"""
Transcriber – lädt das Whisper-Modell asynchron und transkribiert Audio-Arrays.
Das Modell wird in einem Background-Thread geladen, damit der Tray sofort erscheint.
"""
from __future__ import annotations

import os
import threading
from typing import Callable, Optional, Tuple

import numpy as np

MIN_DURATION_SECONDS = 0.3  # Kürzere Aufnahmen werden verworfen

# Beim Erststart muss das Modell (~460 MB) heruntergeladen werden.
# 30 Minuten decken auch sehr langsame Verbindungen ab.
_TIMEOUT_SECONDS = 1800

_TIMEOUT_MESSAGE = (
    "Whisper konnte nicht geladen werden.\n\n"
    "Mögliche Ursachen:\n\n"
    "1. Kein Internetzugang beim Erststart\n"
    "   Das Sprachmodell (~460 MB) muss beim ersten Start heruntergeladen werden.\n"
    "   → Internetzugang prüfen und Blitztext neu starten.\n\n"
    "2. Antivirus blockiert den Download\n"
    "   → Ausnahme für Blitztext im Antivirusprogramm einrichten.\n\n"
    "3. PyTorch-Version nicht kompatibel\n"
    "   → Blitztext neu installieren."
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
        self._on_status_callback: Optional[Callable[[str, str], None]] = None
        self._current_status: Optional[Tuple[str, str]] = None

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

    def set_on_status(self, callback: Callable[[str, str], None]) -> None:
        """Wird mit (title, message) aufgerufen, wenn sich der Ladestatus ändert."""
        self._on_status_callback = callback
        if self._current_status:
            callback(*self._current_status)

    def _notify_status(self, title: str, message: str) -> None:
        self._current_status = (title, message)
        if self._on_status_callback:
            self._on_status_callback(title, message)

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
            "Whisper-Loader Timeout nach %d Sekunden", _TIMEOUT_SECONDS
        )
        if self._on_error_callback:
            self._on_error_callback(_TIMEOUT_MESSAGE)

    @staticmethod
    def _model_cache_path(model_name: str) -> Optional[str]:
        """Gibt den Pfad zur gecachten Modelldatei zurück, oder None falls unbekannt."""
        try:
            import whisper as _w
            url = _w._MODELS.get(model_name, "")
            if not url:
                return None
            download_root = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
            return os.path.join(download_root, os.path.basename(url))
        except Exception:
            return None

    def _load_model(self) -> None:
        import logging
        import torch
        import whisper  # Import hier, damit startup schnell bleibt

        log = logging.getLogger(__name__)
        log.info("Whisper-Loader gestartet (Modell: %s, device-setting: %s)",
                 self._model_name, self._whisper_device)

        # Defekte (leere) Cache-Datei löschen, damit whisper sauber neu lädt
        cache_path = self._model_cache_path(self._model_name)
        if cache_path and os.path.isfile(cache_path) and os.path.getsize(cache_path) < 1024:
            log.warning("Defekte Cache-Datei gefunden (%s, %d Bytes) – wird gelöscht",
                        cache_path, os.path.getsize(cache_path))
            try:
                os.remove(cache_path)
            except OSError as e:
                log.warning("Konnte defekte Cache-Datei nicht löschen: %s", e)

        # Prüfen ob Modell-Download nötig ist
        needs_download = cache_path and not os.path.isfile(cache_path)
        if needs_download:
            log.info("Modell nicht im Cache – Download erforderlich (~460 MB)")
            self._notify_status(
                "Blitztext",
                "Whisper-Modell wird heruntergeladen (~460 MB).\n"
                "Das kann mehrere Minuten dauern …"
            )

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
