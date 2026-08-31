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

import ctypes
import logging
import os
import queue
import sys
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
from blitztext.openai_polish import OpenAIPolishClient
from blitztext.recorder import AudioRecorder
from blitztext.transcriber import Transcriber
from blitztext.tray import IDLE, PROCESSING, RECORDING, TrayApp
from blitztext.updater import check_for_updates

MIN_RECORDING_DURATION = 0.3  # Sekunden


def _create_transcriber(settings):
    """Erstellt das Transkriptions-Backend passend zu settings.transcription_backend.

    Beide Backends (lokal/OpenAI) bieten dieselbe Schnittstelle (is_ready,
    set_on_ready/set_on_error/set_on_status, transcribe, transcribe_file) –
    der Rest der App muss nicht wissen, welches gerade aktiv ist.
    """
    if settings.transcription_backend == "openai":
        from blitztext.openai_transcriber import OpenAITranscriber
        return OpenAITranscriber(
            api_key=settings.openai_api_key,
            model=settings.openai_transcribe_model,
        )
    return Transcriber(
        model_name=settings.whisper_model,
        whisper_device=settings.whisper_device,
    )


class BlitztextApp:
    def __init__(self) -> None:
        self._settings = settings_mod.load()

        # Komponenten
        self._recorder = AudioRecorder()
        self._transcriber = _create_transcriber(self._settings)
        self._claude = ClaudeClient(api_key=self._settings.claude_api_key)
        self._openai_polish = OpenAIPolishClient(api_key=self._settings.openai_api_key)

        self._worker_queue: queue.Queue = queue.Queue()
        self._state_lock = threading.Lock()
        self._is_recording = False
        self._foreground_hwnd = 0
        self._install_dir = os.path.dirname(os.path.abspath(__file__))

        # Tray (läuft auf Main Thread)
        self._tray = TrayApp(
            settings=self._settings,
            on_open_settings=self._open_settings,
            on_toggle_mode=self._toggle_mode,
            on_quit=self._quit,
        )

        # Hotkeys
        self._hotkey_mgr = HotkeyManager(
            bindings={
                "record": (self._settings.hotkey, self._on_hotkey),
                "settings": (self._settings.settings_hotkey, self._open_settings),
            }
        )

        # Transkriptions-Callbacks (lokal oder OpenAI-Cloud, siehe _create_transcriber)
        self._transcriber.set_on_ready(
            lambda: self._tray.notify("Blitztext", "Bereit – Hotkey aktiv.")
        )
        self._transcriber.set_on_error(self._on_whisper_error)
        self._transcriber.set_on_status(
            lambda title, msg: self._tray.notify(title, msg)
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
            if self._settings.transcription_backend == "openai":
                self._tray.notify(
                    "Blitztext", "Kein OpenAI API Key konfiguriert – bitte in den Einstellungen eintragen."
                )
            else:
                self._tray.notify("Blitztext", "Whisper-Modell wird geladen …")

        check_for_updates(
            self._install_dir,
            on_update_found=lambda msg: self._tray.notify("Blitztext – Update", msg),
        )

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
            if self._settings.transcription_backend == "openai":
                self._tray.notify(
                    "Blitztext", "Kein OpenAI API Key konfiguriert – bitte in den Einstellungen eintragen."
                )
            else:
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
    # Textveredelung (Claude oder OpenAI, je nach settings.polish_provider)
    # ------------------------------------------------------------------

    def _reformulate(self, text: str, mode: str) -> str:
        if self._settings.polish_provider == "openai":
            return self._openai_polish.reformulate(text, mode=mode)
        return self._claude.reformulate(text, mode=mode)

    def _space_leak_count(self) -> int:
        """Anzahl geschützter Leerzeichen, die durch den Aufnahme-Hotkey ins
        Zielfenster durchgerutscht sein können (Strg+Umschalt+Leertaste ist die
        native Windows/Office-Tastenkombination für ein geschütztes Leerzeichen –
        einmal beim Start-, einmal beim Stopp-Tastendruck). 0, wenn der Hotkey
        keine Leertaste enthält."""
        return self._settings.hotkey.lower().split("+").count("space") * 2

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
                if self._settings.mode in ("poliert_konservativ", "poliert_ausgefeilt"):
                    try:
                        text = self._reformulate(text, self._settings.mode)
                        log.info("Textveredelung-Ergebnis: %r", text)
                    except MissingAPIKeyError:
                        provider = "OpenAI" if self._settings.polish_provider == "openai" else "Claude"
                        self._tray.notify(
                            "Blitztext",
                            f"Kein {provider} API Key – Text wird unverändert eingefügt.",
                        )
                    except Exception as e:
                        log.exception("Textveredelung-Fehler")
                        self._tray.notify(
                            "Blitztext",
                            f"Textveredelung-Fehler: {e} – Text wird unverändert eingefügt.",
                        )

                insert(text, hwnd=hwnd, delete_before=self._space_leak_count())
                log.info("Text eingefügt")

            except Exception as e:
                log.exception("Worker-Fehler")
                self._tray.notify("Blitztext", f"Fehler: {e}")
            finally:
                self._tray.set_state(IDLE)

    # ------------------------------------------------------------------
    # Einstellungen
    # ------------------------------------------------------------------

    def _on_whisper_error(self, message: str) -> None:
        log.error("Transkriptions-Backend-Fehler: %s", message)
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Blitztext – Spracherkennung nicht bereit", message)
        root.destroy()

    def _on_transcribe_file(self, file_path: str) -> None:
        """Startet die Datei-Transkription in einem eigenen Thread."""
        t = threading.Thread(
            target=self._transcribe_file_worker,
            args=(file_path,),
            daemon=True,
            name="FileTranscriber",
        )
        t.start()

    def _transcribe_file_worker(self, file_path: str) -> None:
        import pyperclip
        self._tray.set_state(PROCESSING)
        try:
            text = self._transcriber.transcribe_file(
                file_path, language=self._settings.language
            )
            log.info("Datei-Transkription: %r", text)

            if not text:
                self._tray.notify("Blitztext", "Keine Sprache erkannt.")
                return

            if self._settings.mode in ("poliert_konservativ", "poliert_ausgefeilt"):
                try:
                    text = self._reformulate(text, self._settings.mode)
                    log.info("Textveredelung-Ergebnis (Datei): %r", text)
                except MissingAPIKeyError:
                    provider = "OpenAI" if self._settings.polish_provider == "openai" else "Claude"
                    self._tray.notify(
                        "Blitztext", f"Kein {provider} API Key – Text wird unverändert kopiert."
                    )
                except Exception as e:
                    log.exception("Textveredelung-Fehler bei Datei-Transkription")
                    self._tray.notify("Blitztext", f"Textveredelung-Fehler: {e}")

            pyperclip.copy(text)
            self._tray.notify("Blitztext", "Text in Zwischenablage – mit Ctrl+V einfügen.")

        except Exception as e:
            log.exception("Fehler bei Datei-Transkription")
            self._tray.notify("Blitztext", f"Fehler: {e}")
        finally:
            self._tray.set_state(IDLE)

    def _open_settings(self) -> None:
        from blitztext.settings_window import open_settings

        open_settings(
            settings=self._settings,
            on_save=self._apply_settings,
            on_transcribe_file=self._on_transcribe_file,
            install_dir=self._install_dir,
        )

    def _apply_settings(self, new_settings) -> None:
        old_backend = self._settings.transcription_backend
        self._settings = new_settings
        self._claude.update_api_key(new_settings.claude_api_key)
        self._openai_polish.update_api_key(new_settings.openai_api_key)
        self._hotkey_mgr.update_hotkey("record", new_settings.hotkey)
        self._hotkey_mgr.update_hotkey("settings", new_settings.settings_hotkey)
        self._tray.update_settings(new_settings)

        if new_settings.transcription_backend != old_backend:
            self._tray.notify(
                "Blitztext",
                "Wechsel der Spracherkennung wird erst nach einem Neustart von Blitztext aktiv.",
            )
        elif new_settings.transcription_backend == "openai":
            # Key/Modell-Änderung wirkt beim Cloud-Backend sofort, kein Neustart nötig.
            self._transcriber.update_api_key(new_settings.openai_api_key)
            self._transcriber.update_model(new_settings.openai_transcribe_model)

    def _toggle_mode(self) -> None:
        self._settings.mode = (
            "poliert_konservativ" if self._settings.mode == "direkt" else "direkt"
        )
        settings_mod.save(self._settings)
        self._tray.update_settings(self._settings)
        mode_label = "Direkt" if self._settings.mode == "direkt" else "Poliert"
        self._tray.notify("Blitztext", f"Modus gewechselt: {mode_label}")


def _ensure_single_instance() -> None:
    """Beendet den Prozess sofort, wenn bereits eine Instanz läuft."""
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "BlitztextSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
    # Handle absichtlich nicht freigeben – bleibt bis Prozessende aktiv


if __name__ == "__main__":
    _ensure_single_instance()
    overlay.start()
    app = BlitztextApp()
    app.run()
