"""
OpenAITranscriber – transkribiert Audio über die OpenAI-Audio-API (Cloud).

Bietet dieselbe Schnittstelle wie transcriber.Transcriber (is_ready,
set_on_ready/set_on_error/set_on_status, transcribe, transcribe_file), damit
main.py zwischen lokalem und Cloud-Backend wechseln kann, ohne den
Worker-Loop anzupassen.

Anders als beim lokalen Backend gibt es kein Modell zu laden: sobald ein
API-Key gesetzt ist, ist das Backend sofort einsatzbereit.
"""
from __future__ import annotations

import io
import logging
import os
import wave
from typing import Callable, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

MIN_DURATION_SECONDS = 0.3  # Kürzere Aufnahmen werden verworfen
SAMPLE_RATE = 16_000

# Limit der OpenAI-Audio-API für Datei-Uploads
_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

_API_TIMEOUT_SECONDS = 120.0


class MissingAPIKeyError(Exception):
    """Wird geworfen, wenn kein OpenAI API Key konfiguriert ist."""


def _float32_to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wandelt ein float32-Mono-Array (-1..1) in WAV-Bytes (16-bit PCM) um – in-memory,
    kein ffmpeg nötig."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


class OpenAITranscriber:
    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini-transcribe") -> None:
        self._api_key = api_key
        self._model = model
        self._client = None
        self._on_ready_callback: Optional[Callable[[], None]] = None
        self._on_error_callback: Optional[Callable[[str], None]] = None
        self._on_status_callback: Optional[Callable[[str, str], None]] = None
        self._current_status: Optional[Tuple[str, str]] = None

    # ------------------------------------------------------------------
    # Öffentliche API – Signatur kompatibel zu transcriber.Transcriber
    # ------------------------------------------------------------------

    def set_on_ready(self, callback: Callable[[], None]) -> None:
        self._on_ready_callback = callback
        if self.is_ready:
            callback()

    def set_on_error(self, callback: Callable[[str], None]) -> None:
        self._on_error_callback = callback
        if not self.is_ready:
            callback(
                "Kein OpenAI API Key konfiguriert.\n\n"
                "Bitte in den Einstellungen unter 'Spracherkennung – OpenAI-Cloud' "
                "einen API Key eintragen."
            )

    def set_on_status(self, callback: Callable[[str, str], None]) -> None:
        self._on_status_callback = callback
        if self._current_status:
            callback(*self._current_status)

    def update_api_key(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None  # Client bei neuem Key neu erstellen

    def update_model(self, model: str) -> None:
        self._model = model

    @property
    def is_ready(self) -> bool:
        # Kein Modell-Laden nötig – mit gesetztem Key ist das Backend sofort nutzbar.
        return bool(self._api_key)

    def transcribe(self, audio: np.ndarray, language: str = "de") -> str:
        """
        Transkribiert ein float32-NumPy-Array (16 kHz, Mono) über die OpenAI-API.
        Gibt einen leeren String zurück, wenn die Aufnahme zu kurz ist.
        """
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION_SECONDS:
            return ""
        wav_bytes = _float32_to_wav_bytes(audio)
        return self._call_api(("aufnahme.wav", wav_bytes), language)

    def transcribe_file(self, file_path: str, language: str = "de") -> str:
        """Lädt eine Audio-Datei hoch und transkribiert sie über die OpenAI-API."""
        size = os.path.getsize(file_path)
        if size > _MAX_FILE_SIZE_BYTES:
            raise RuntimeError(
                f"Datei zu groß für Cloud-Transkription "
                f"({size / 1024 / 1024:.1f} MB, Limit 25 MB) – "
                f"bitte lokales Backend verwenden."
            )
        with open(file_path, "rb") as f:
            data = f.read()
        return self._call_api((os.path.basename(file_path), data), language)

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    def _client_or_raise(self):
        if not self._api_key:
            raise MissingAPIKeyError("Kein OpenAI API Key konfiguriert.")
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self._api_key, timeout=_API_TIMEOUT_SECONDS)
        return self._client

    def _call_api(self, file_tuple: Tuple[str, bytes], language: str) -> str:
        client = self._client_or_raise()
        kwargs: dict = {"model": self._model, "file": file_tuple}
        if language:
            kwargs["language"] = language

        try:
            result = client.audio.transcriptions.create(**kwargs)
        except Exception as e:
            log.exception("OpenAI-Transkription fehlgeschlagen")
            raise RuntimeError(self._friendly_error(e)) from e

        text = getattr(result, "text", None)
        if text is None and isinstance(result, dict):
            text = result.get("text", "")
        return (text or "").strip()

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        name = type(e).__name__
        if name == "AuthenticationError":
            return "OpenAI API Key ungültig – bitte in den Einstellungen prüfen."
        if name == "RateLimitError":
            return "OpenAI-Kontingent überschritten (Rate-Limit oder Guthaben aufgebraucht)."
        if name in ("APITimeoutError", "APIConnectionError"):
            return "Verbindung zu OpenAI fehlgeschlagen oder Zeitüberschreitung – bitte erneut versuchen."
        return f"OpenAI-Fehler: {e}"
