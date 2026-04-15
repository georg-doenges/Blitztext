"""
Blitztext – Einstiegspunkt.

Startet alle Komponenten und übergibt die Kontrolle an den pystray-Loop
(der auf dem Main Thread laufen muss).

Threading-Übersicht:
  Main Thread   → pystray event loop
  Worker Thread → Whisper + Claude + Text einfügen
  Hotkey Thread → pynput GlobalHotKeys (von pynput verwaltet)
  Audio Thread  → sounddevice PortAudio Callback (von sounddevice verwaltet)
  Whisper Load  → einmaliger Background-Thread beim Start
"""
from __future__ import annotations

import logging
import os
import queue
import threading

from blitztext import overlay, settings as settings_mod


def _setup_logging() -> None:
    log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Blitztext")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "blitztext.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


_setup_logging()
log = logging.getLogger(__name__)
from blitztext.claude_client import ClaudeClient, MissingAPIKeyError
from blitztext.hotkey import HotkeyManager
from blitztext.inserter import get_foreground_hwnd, insert
from blitztext.recorder import AudioRecorder
from blitztext.transcriber import Transcriber
from blitztext.tray import IDLE, PROCESSING, RECORDING, TrayApp

MIN_RECORDING_DURATION = 0.3  # Sekunden


class BlitztextApp:
    def __init__(self) -> None:
        self._settings = settings_mod.load()

        # Komponenten
        self._recorder = AudioRecorder()
        self._transcriber = Transcriber(model_name=self._settings.whisper_model)
        self._claude = ClaudeClient(api_key=self._settings.claude_api_key)

        self._worker_queue: queue.Queue = queue.Queue()
        self._state_lock = threading.Lock()
        self._is_recording = False

        # Tray (läuft auf Main Thread)
        self._tray = TrayApp(
            settings=self._settings,
            on_open_settings=self._open_settings,
            on_toggle_mode=self._toggle_mode,
            on_quit=self._quit,
        )

        # Hotkey
        self._hotkey_mgr = HotkeyManager(
            hotkey_str=self._settings.hotkey,
            on_activate=self._on_hotkey,
        )

        # Whisper-Bereit-Callback
        self._transcriber.set_on_ready(
            lambda: self._tray.notify(
                "Blitztext", "Whisper bereit – Hotkey aktiv."
            )
        )

        # Worker Thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="BlitztextWorker",
        )

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Startet alle Threads und übergibt Kontrolle an den Tray-Loop."""
        self._hotkey_mgr.start()
        self._worker_thread.start()

        if not self._transcriber.is_ready:
            self._tray.notify("Blitztext", "Whisper-Modell wird geladen …")

        # Blockiert bis zum Beenden
        self._tray.run()

    def _quit(self) -> None:
        self._hotkey_mgr.stop()
        if self._is_recording:
            self._recorder.stop()
        self._tray.stop()

    # ------------------------------------------------------------------
    # Hotkey-Handler (läuft auf pynput-Thread)
    # ------------------------------------------------------------------

    def _on_hotkey(self) -> None:
        with self._state_lock:
            if not self._is_recording:
                self._start_recording()
            else:
                self._stop_recording()

    def _start_recording(self) -> None:
        if not self._transcriber.is_ready:
            self._tray.notify("Blitztext", "Whisper wird noch geladen, bitte warten …")
            return

        self._is_recording = True
        self._foreground_hwnd = get_foreground_hwnd()
        self._recorder.start()
        self._tray.set_state(RECORDING)
        log.info("Aufnahme gestartet (hwnd=%s)", self._foreground_hwnd)

    def _stop_recording(self) -> None:
        self._is_recording = False
        audio = self._recorder.stop()
        duration = len(audio) / 16_000
        log.info("Aufnahme gestoppt (%.1f s)", duration)
        self._tray.set_state(PROCESSING)
        self._worker_queue.put((audio, self._foreground_hwnd))

    # ------------------------------------------------------------------
    # Worker Loop (läuft auf Worker Thread)
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        import numpy as np

        while True:
            try:
                audio, hwnd = self._worker_queue.get()
            except Exception:
                continue

            try:
                duration = len(audio) / 16_000
                if duration < MIN_RECORDING_DURATION:
                    self._tray.notify(
                        "Blitztext", "Aufnahme zu kurz – bitte länger sprechen."
                    )
                    self._tray.set_state(IDLE)
                    continue

                # Transkription
                text = self._transcriber.transcribe(
                    audio, language=self._settings.language
                )
                log.info("Transkription: %r", text)

                if not text:
                    self._tray.set_state(IDLE)
                    continue

                # Modus
                if self._settings.mode == "poliert":
                    try:
                        text = self._claude.reformulate(text)
                        log.info("Claude-Ergebnis: %r", text)
                    except MissingAPIKeyError:
                        self._tray.notify(
                            "Blitztext",
                            "Kein Claude API Key – Text wird unverändert eingefügt.",
                        )
                    except Exception as e:
                        log.exception("Claude-Fehler")
                        self._tray.notify(
                            "Blitztext",
                            f"Claude-Fehler: {e} – Text wird unverändert eingefügt.",
                        )

                insert(text, hwnd=hwnd)
                log.info("Text eingefügt")

            except Exception as e:
                log.exception("Worker-Fehler")
                self._tray.notify("Blitztext", f"Fehler: {e}")
            finally:
                self._tray.set_state(IDLE)

    # ------------------------------------------------------------------
    # Einstellungen
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        from blitztext.settings_window import open_settings

        open_settings(
            settings=self._settings,
            on_save=self._apply_settings,
        )

    def _apply_settings(self, new_settings) -> None:
        self._settings = new_settings
        self._claude.update_api_key(new_settings.claude_api_key)
        self._hotkey_mgr.update_hotkey(new_settings.hotkey)
        self._tray.update_settings(new_settings)

    def _toggle_mode(self) -> None:
        self._settings.mode = (
            "poliert" if self._settings.mode == "direkt" else "direkt"
        )
        settings_mod.save(self._settings)
        self._tray.update_settings(self._settings)
        mode_label = "Poliert" if self._settings.mode == "poliert" else "Direkt"
        self._tray.notify("Blitztext", f"Modus gewechselt: {mode_label}")


if __name__ == "__main__":
    overlay.start()
    app = BlitztextApp()
    app.run()
