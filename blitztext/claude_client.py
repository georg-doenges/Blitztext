"""
ClaudeClient – sendet Whisper-Transkriptionen zur Umformulierung an die Claude API.
Wird nur in den Poliert-Modi verwendet.
"""
from __future__ import annotations

# Konservativ: minimale Eingriffe – nur offensichtliche Fehler, Dopplungen, Füllwörter
SYSTEM_PROMPT_KONSERVATIV = (
    "Du bist ein zurückhaltender Texteditor. Der Benutzer gibt dir einen rohen "
    "Sprach-zu-Text-Transkript. Deine Aufgabe ist es, NUR folgendes zu korrigieren: "
    "offensichtliche Grammatik- und Rechtschreibfehler, Füllwörter ('ähm', 'also', "
    "'sozusagen', 'halt', 'quasi'), direkte Wortwiederholungen und eindeutig verunglückte "
    "Formulierungen. Behalte Stil, Tonalität, Wortwahl und Struktur des Originals so weit "
    "wie möglich bei. Verändere NICHTS, was korrekt ist. "
    "Gib NUR den bereinigten Text aus – keine Erklärungen, keine Kommentare."
)

# Ausgefeilt: vollständige Überarbeitung inkl. Formatierung (z.B. E-Mails)
SYSTEM_PROMPT_AUSGEFEILT = (
    "Du bist ein professioneller Texter. Der Benutzer gibt dir einen rohen "
    "Sprach-zu-Text-Transkript. Formuliere den Text zu einer sauberen, professionellen "
    "Fassung um: korrigiere Grammatik und Zeichensetzung, optimiere Formulierungen, "
    "strukturiere den Text in sinnvolle Absätze. "
    "Wenn der Text eine E-Mail ist, formatiere sie korrekt: Anrede (z.B. 'Lieber Herr …') "
    "als eigene Zeile, Fließtext, Abschlussformel und Grußzeile jeweils abgesetzt. "
    "Behalte die Sprache des Originals bei (Deutsch bleibt Deutsch, Englisch bleibt Englisch). "
    "Gib NUR den fertigen Text aus – keine Erklärungen, keine Kommentare."
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

    def reformulate(self, text: str, mode: str = "poliert_konservativ") -> str:
        """
        Sendet *text* an Claude und gibt den umformulierten Text zurück.
        mode: "poliert_konservativ" | "poliert_ausgefeilt"
        Wirft MissingAPIKeyError, wenn kein API-Key gesetzt ist.
        """
        if not self._api_key:
            raise MissingAPIKeyError("Kein Claude API Key konfiguriert.")

        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)

        system = (
            SYSTEM_PROMPT_AUSGEFEILT
            if mode == "poliert_ausgefeilt"
            else SYSTEM_PROMPT_KONSERVATIV
        )

        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        return message.content[0].text.strip()
