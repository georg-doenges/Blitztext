"""
OpenAIPolishClient – sendet Whisper-Transkriptionen zur Umformulierung an die
OpenAI Chat Completions API. Alternative zu ClaudeClient, aktiv wenn
settings.polish_provider == "openai".

Nutzt denselben openai_api_key wie die Cloud-Spracherkennung (ein OpenAI-
Account, ein Key für beide Zwecke) – siehe openai_transcriber.py.
"""
from __future__ import annotations

from blitztext.claude_client import (
    MissingAPIKeyError,
    SYSTEM_PROMPT_AUSGEFEILT,
    SYSTEM_PROMPT_KONSERVATIV,
)

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIPolishClient:
    def __init__(self, api_key: str = "", model: str = _DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    def update_api_key(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None  # Client bei neuem Key neu erstellen

    def reformulate(self, text: str, mode: str = "poliert_konservativ") -> str:
        """
        Sendet *text* an OpenAI und gibt den umformulierten Text zurück.
        mode: "poliert_konservativ" | "poliert_ausgefeilt"
        Wirft MissingAPIKeyError, wenn kein API-Key gesetzt ist.
        """
        if not self._api_key:
            raise MissingAPIKeyError("Kein OpenAI API Key konfiguriert.")

        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self._api_key)

        system = (
            SYSTEM_PROMPT_AUSGEFEILT
            if mode == "poliert_ausgefeilt"
            else SYSTEM_PROMPT_KONSERVATIV
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=8192,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            )
        except Exception as e:
            raise RuntimeError(self._friendly_error(e)) from e

        return response.choices[0].message.content.strip()

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
