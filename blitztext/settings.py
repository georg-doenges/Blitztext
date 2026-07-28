r"""
Settings – lädt und speichert die Konfiguration unter %APPDATA%\Blitztext\settings.json.
Atomisches Schreiben über temporäre Datei verhindert Datenverlust bei Absturz.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field


def _config_dir() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "Blitztext")


def _config_path() -> str:
    return os.path.join(_config_dir(), "settings.json")


@dataclass
class Settings:
    hotkey: str = "ctrl+shift+space"
    settings_hotkey: str = "ctrl+shift+minus"  # öffnet das Einstellungsfenster
    mode: str = "direkt"          # "direkt" | "poliert_konservativ" | "poliert_ausgefeilt"
    polish_provider: str = "claude"  # "claude" | "openai" – nur relevant, wenn mode != "direkt"
    claude_api_key: str = ""
    autostart: bool = False
    language: str = "de"          # Whisper-Sprachcode oder "" für auto-detect
    whisper_model: str = "small"
    whisper_device: str = "auto"  # "auto" = CUDA wenn verfügbar, "cpu" = immer CPU
    transcription_backend: str = "local"  # "local" = Whisper auf diesem Rechner, "openai" = OpenAI-API
    openai_api_key: str = ""
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"  # "whisper-1" | "gpt-4o-mini-transcribe" | "gpt-4o-transcribe"


def load() -> Settings:
    path = _config_path()
    if not os.path.exists(path):
        return Settings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults = asdict(Settings())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        # Rückwärtskompatibilität: altes "poliert" → "poliert_konservativ"
        if defaults.get("mode") == "poliert":
            defaults["mode"] = "poliert_konservativ"
        return Settings(**defaults)
    except Exception:
        return Settings()


def save(settings: Settings) -> None:
    directory = _config_dir()
    os.makedirs(directory, exist_ok=True)
    path = _config_path()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)
