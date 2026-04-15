"""
ClaudeClient – sendet Whisper-Transkriptionen zur Umformulierung an die Claude API.
Wird nur im Modus "Poliert" verwendet.
"""
from __future__ import annotations

SYSTEM_PROMPT = (
    "Du bist ein Texteditor. Der Benutzer gibt dir einen rohen Sprach-zu-Text-Transkript "
    "(ggf. mit Sprachfehlern, Füllwörtern, Wiederholungen, unvollständigen Sätzen). "
    "Formuliere den Text zu einem sauberen, grammatikalisch korrekten Text in derselben "
    "Sprache um. Entferne Füllwörter ('ähm', 'also', 'sozusagen'), korrigiere Satzstruktur "
    "und Zeichensetzung. Gib NUR den bereinigten Text aus – keine Erklärungen, "
    "keine Anführungszeichen, keine zusätzlichen Kommentare."
)


class MissingAPIKeyError(Exception):
    """Wird geworfen, wenn kein Claude API Key konfiguriert ist."""


class ClaudeClient:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._client = None

    def update_api_key(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None  # Client bei neuem Key neu erstellen

    def reformulate(self, text: str) -> str:
        """
        Sendet *text* an Claude und gibt den umformulierten Text zurück.
        Wirft MissingAPIKeyError, wenn kein API-Key gesetzt ist.
        """
        if not self._api_key:
            raise MissingAPIKeyError("Kein Claude API Key konfiguriert.")

        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)

        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        return message.content[0].text.strip()
