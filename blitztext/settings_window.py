"""
SettingsWindow – tkinter-Einstellungsfenster.

Läuft in einem eigenen Thread (tkinter ist nicht thread-safe).
Singleton-Guard verhindert mehrere gleichzeitig offene Fenster.

Gliederung in vier Blöcke (LabelFrames): Aufnahme, Spracherkennung
(Lokal/OpenAI-Cloud), Textveredelung (optional), System.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from blitztext.settings import Settings

_window_thread: Optional[threading.Thread] = None
_window_instance: Optional["SettingsWindow"] = None
_lock = threading.Lock()

_OPENAI_MODELS = ["gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1"]


def open_settings(
    settings: "Settings",
    on_save: Callable[["Settings"], None],
    on_transcribe_file: Optional[Callable[[str], None]] = None,
) -> None:
    """Öffnet das Settings-Fenster in einem eigenen Thread (Singleton)."""
    global _window_thread, _window_instance

    with _lock:
        if _window_thread is not None and _window_thread.is_alive():
            # Bereits offen → in den Vordergrund bringen
            if _window_instance is not None:
                _window_instance.lift()
            return

        _window_thread = threading.Thread(
            target=_run_window,
            args=(settings, on_save, on_transcribe_file),
            daemon=True,
            name="SettingsWindow",
        )
        _window_thread.start()


def _run_window(
    settings: "Settings",
    on_save: Callable[["Settings"], None],
    on_transcribe_file: Optional[Callable[[str], None]],
) -> None:
    global _window_instance
    import gc
    win = SettingsWindow(settings, on_save, on_transcribe_file)
    _window_instance = win
    try:
        win.mainloop()
    finally:
        _window_instance = None
        # GC auf diesem Thread erzwingen, damit tkinter-Variable.__del__
        # nicht vom falschen Thread aufgerufen wird.
        win = None
        gc.collect()


class SettingsWindow(tk.Tk):
    def __init__(
        self,
        settings: "Settings",
        on_save: Callable[["Settings"], None],
        on_transcribe_file: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_save = on_save
        self._on_transcribe_file = on_transcribe_file
        self._capturing_hotkey = False

        self.title("Blitztext – Einstellungen")
        self.resizable(False, False)
        self._build_ui()
        self._center()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_aufnahme_section(container, pad)
        self._build_spracherkennung_section(container, pad)
        self._build_textveredelung_section(container, pad)
        self._build_system_section(container, pad)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=(8, 0))
        ttk.Button(btn_frame, text="Speichern", command=self._save).pack(
            side="left", padx=8
        )
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(
            side="left", padx=8
        )

        # Anfangssichtbarkeit der bedingten Detailblöcke setzen
        self._on_backend_change()
        self._on_mode_change()

    def _build_aufnahme_section(self, parent: tk.Widget, pad: dict) -> None:
        frame = ttk.LabelFrame(parent, text="Aufnahme")
        frame.pack(fill="x", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Tastenkombination:").grid(
            row=0, column=0, sticky="w", **pad
        )
        self._hotkey_var = tk.StringVar(master=self, value=self._settings.hotkey)
        self._hotkey_entry = ttk.Entry(
            frame, textvariable=self._hotkey_var, width=24, state="readonly"
        )
        self._hotkey_entry.grid(row=0, column=1, sticky="ew", **pad)
        self._record_btn = ttk.Button(
            frame, text="Aufnehmen", command=self._start_hotkey_capture
        )
        self._record_btn.grid(row=0, column=2, **pad)

        self._hotkey_hint = ttk.Label(frame, text="", foreground="gray")
        self._hotkey_hint.grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(frame, text="Sprache (Whisper):").grid(
            row=2, column=0, sticky="w", **pad
        )
        self._lang_var = tk.StringVar(master=self, value=self._settings.language)
        lang_cb = ttk.Combobox(
            frame,
            textvariable=self._lang_var,
            values=["de", "en", "fr", "es", "it", ""],
            width=8,
            state="readonly",
        )
        lang_cb.grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(frame, text="(leer = auto)", foreground="gray").grid(
            row=2, column=2, sticky="w"
        )

    def _build_spracherkennung_section(self, parent: tk.Widget, pad: dict) -> None:
        frame = ttk.LabelFrame(parent, text="Spracherkennung")
        frame.pack(fill="x", pady=(0, 8))

        self._backend_var = tk.StringVar(
            master=self, value=self._settings.transcription_backend
        )

        # --- Lokal ---
        ttk.Radiobutton(
            frame, text="Lokal (Whisper auf diesem Rechner)",
            variable=self._backend_var, value="local",
            command=self._on_backend_change,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        self._local_sub = ttk.Frame(frame)
        self._local_sub.grid(row=1, column=0, sticky="w", padx=(28, 10))
        local_sub = self._local_sub

        ttk.Label(local_sub, text="Modell:").grid(row=0, column=0, sticky="w", pady=2)
        self._whisper_model_var = tk.StringVar(
            master=self, value=self._settings.whisper_model
        )
        self._whisper_model_cb = ttk.Combobox(
            local_sub,
            textvariable=self._whisper_model_var,
            values=["tiny", "base", "small", "medium", "large"],
            width=8,
            state="readonly",
        )
        self._whisper_model_cb.grid(row=0, column=1, sticky="w", padx=(4, 16))

        ttk.Label(local_sub, text="Gerät:").grid(row=0, column=2, sticky="w")
        self._whisper_device_var = tk.StringVar(
            master=self, value=self._settings.whisper_device
        )
        self._whisper_device_cb = ttk.Combobox(
            local_sub,
            textvariable=self._whisper_device_var,
            values=["auto", "cpu", "cuda"],
            width=8,
            state="readonly",
        )
        self._whisper_device_cb.grid(row=0, column=3, sticky="w", padx=(4, 0))

        ttk.Label(local_sub, text="(Neustart erforderlich)", foreground="gray").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(2, 6)
        )

        ttk.Separator(frame, orient="horizontal").grid(
            row=2, column=0, sticky="ew", padx=10, pady=4
        )

        # --- OpenAI-Cloud ---
        ttk.Radiobutton(
            frame, text="OpenAI-Cloud (API-Key erforderlich)",
            variable=self._backend_var, value="openai",
            command=self._on_backend_change,
        ).grid(row=3, column=0, sticky="w", padx=10, pady=(2, 2))

        self._openai_sub = ttk.Frame(frame)
        self._openai_sub.grid(row=4, column=0, sticky="w", padx=(28, 10), pady=(0, 8))
        openai_sub = self._openai_sub

        ttk.Label(openai_sub, text="Modell:").grid(row=0, column=0, sticky="w", pady=2)
        self._openai_model_var = tk.StringVar(
            master=self, value=self._settings.openai_transcribe_model
        )
        self._openai_model_cb = ttk.Combobox(
            openai_sub,
            textvariable=self._openai_model_var,
            values=_OPENAI_MODELS,
            width=22,
            state="readonly",
        )
        self._openai_model_cb.grid(row=0, column=1, sticky="w", padx=(4, 0))

        ttk.Label(openai_sub, text="OpenAI API Key:").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        self._openai_key_var = tk.StringVar(
            master=self, value=self._settings.openai_api_key
        )
        self._openai_key_entry = ttk.Entry(
            openai_sub, textvariable=self._openai_key_var, show="*", width=28
        )
        self._openai_key_entry.grid(row=1, column=1, sticky="w", padx=(4, 6), pady=(6, 0))
        self._show_openai_key = False
        self._openai_key_toggle_btn = ttk.Button(
            openai_sub, text="Anzeigen", command=self._toggle_openai_key_visibility
        )
        self._openai_key_toggle_btn.grid(row=1, column=2, sticky="w", pady=(6, 0))

    def _build_textveredelung_section(self, parent: tk.Widget, pad: dict) -> None:
        frame = ttk.LabelFrame(parent, text="Textveredelung (optional)")
        frame.pack(fill="x", pady=(0, 8))

        self._mode_var = tk.StringVar(master=self, value=self._settings.mode)
        ttk.Radiobutton(
            frame, text="Direkt (keine Nachbearbeitung)",
            variable=self._mode_var, value="direkt", command=self._on_mode_change,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        ttk.Radiobutton(
            frame, text="Poliert – Konservativ  (nur Fehler & Füllwörter)",
            variable=self._mode_var, value="poliert_konservativ", command=self._on_mode_change,
        ).grid(row=1, column=0, sticky="w", padx=10, pady=2)
        ttk.Radiobutton(
            frame, text="Poliert – Ausgefeilt  (vollständige Überarbeitung, E-Mail-Format)",
            variable=self._mode_var, value="poliert_ausgefeilt", command=self._on_mode_change,
        ).grid(row=2, column=0, sticky="w", padx=10, pady=2)

        # --- Anbieter + API Key (nur sichtbar, wenn ein Poliert-Modus gewählt ist) ---
        self._provider_sub = ttk.Frame(frame)
        self._provider_sub.grid(row=3, column=0, sticky="w", padx=(28, 10), pady=(4, 8))

        self._polish_provider_var = tk.StringVar(
            master=self, value=self._settings.polish_provider
        )
        ttk.Label(self._provider_sub, text="Anbieter:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            self._provider_sub, text="Claude",
            variable=self._polish_provider_var, value="claude",
            command=self._on_polish_provider_change,
        ).grid(row=0, column=1, sticky="w", padx=(6, 12))
        ttk.Radiobutton(
            self._provider_sub, text="OpenAI",
            variable=self._polish_provider_var, value="openai",
            command=self._on_polish_provider_change,
        ).grid(row=0, column=2, sticky="w")

        # Claude-Key-Zeile
        self._claude_key_row = ttk.Frame(self._provider_sub)
        self._claude_key_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(self._claude_key_row, text="Claude API Key:").grid(row=0, column=0, sticky="w")
        self._api_key_var = tk.StringVar(master=self, value=self._settings.claude_api_key)
        self._api_entry = ttk.Entry(
            self._claude_key_row, textvariable=self._api_key_var, show="*", width=28
        )
        self._api_entry.grid(row=0, column=1, sticky="w", padx=(6, 6))
        self._show_key = False
        ttk.Button(
            self._claude_key_row, text="Anzeigen", command=self._toggle_key_visibility
        ).grid(row=0, column=2, sticky="w")

        # OpenAI-Key-Zeile – nutzt dieselbe Variable wie im Spracherkennungs-Block,
        # damit derselbe Key an beiden Stellen automatisch synchron bleibt.
        self._openai_key_row = ttk.Frame(self._provider_sub)
        self._openai_key_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(self._openai_key_row, text="OpenAI API Key:").grid(row=0, column=0, sticky="w")
        self._openai_key_entry_polish = ttk.Entry(
            self._openai_key_row, textvariable=self._openai_key_var, show="*", width=28
        )
        self._openai_key_entry_polish.grid(row=0, column=1, sticky="w", padx=(6, 6))
        self._show_openai_key_polish = False
        ttk.Button(
            self._openai_key_row, text="Anzeigen",
            command=self._toggle_openai_key_polish_visibility,
        ).grid(row=0, column=2, sticky="w")

    def _build_system_section(self, parent: tk.Widget, pad: dict) -> None:
        frame = ttk.LabelFrame(parent, text="System")
        frame.pack(fill="x", pady=(0, 0))

        from blitztext import autostart
        self._autostart_var = tk.BooleanVar(master=self, value=autostart.is_enabled())
        ttk.Checkbutton(
            frame, text="Mit Windows starten", variable=self._autostart_var
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        utils_frame = ttk.Frame(frame)
        utils_frame.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        ttk.Button(utils_frame, text="Log anzeigen", command=self._open_log).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(
            utils_frame,
            text="Audio-Datei transkribieren …",
            command=self._pick_and_transcribe_file,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Spracherkennung: Details nur fuer das gewaehlte Backend einblenden
    # ------------------------------------------------------------------

    def _on_backend_change(self) -> None:
        if self._backend_var.get() == "local":
            self._openai_sub.grid_remove()
            self._local_sub.grid()
        else:
            self._local_sub.grid_remove()
            self._openai_sub.grid()

    def _toggle_openai_key_visibility(self) -> None:
        self._show_openai_key = not self._show_openai_key
        self._openai_key_entry.config(show="" if self._show_openai_key else "*")

    # ------------------------------------------------------------------
    # Textveredelung: Anbieter/Key-Zeile nur bei Poliert-Modus einblenden
    # ------------------------------------------------------------------

    def _on_mode_change(self) -> None:
        if self._mode_var.get() == "direkt":
            self._provider_sub.grid_remove()
        else:
            self._provider_sub.grid()
            self._on_polish_provider_change()

    def _on_polish_provider_change(self) -> None:
        if self._polish_provider_var.get() == "claude":
            self._openai_key_row.grid_remove()
            self._claude_key_row.grid()
        else:
            self._claude_key_row.grid_remove()
            self._openai_key_row.grid()

    def _toggle_openai_key_polish_visibility(self) -> None:
        self._show_openai_key_polish = not self._show_openai_key_polish
        self._openai_key_entry_polish.config(show="" if self._show_openai_key_polish else "*")

    # ------------------------------------------------------------------
    # Hotkey-Aufnahme
    # ------------------------------------------------------------------

    def _start_hotkey_capture(self) -> None:
        self._capturing_hotkey = True
        self._hotkey_hint.config(
            text="Tastenkombination drücken … (Esc zum Abbrechen)", foreground="blue"
        )
        self._record_btn.config(state="disabled")
        self._hotkey_var.set("")
        self._pressed_keys: set = set()
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)

    def _on_key_press(self, event: tk.Event) -> None:
        if not self._capturing_hotkey:
            return
        key = event.keysym.lower()
        if key == "escape":
            self._cancel_hotkey_capture()
            return
        self._pressed_keys.add(key)
        self._hotkey_var.set("+".join(sorted(self._pressed_keys)))

    def _on_key_release(self, event: tk.Event) -> None:
        if not self._capturing_hotkey:
            return
        # Bei Loslassen aller Tasten → Aufnahme abschließen
        key = event.keysym.lower()
        self._pressed_keys.discard(key)
        if not self._pressed_keys and self._hotkey_var.get():
            self._finish_hotkey_capture()

    def _finish_hotkey_capture(self) -> None:
        self._capturing_hotkey = False
        self.unbind("<KeyPress>")
        self.unbind("<KeyRelease>")
        self._hotkey_hint.config(text="✓ Gespeichert", foreground="green")
        self._record_btn.config(state="normal")
        self.after(2000, lambda: self._hotkey_hint.config(text=""))

    def _cancel_hotkey_capture(self) -> None:
        self._capturing_hotkey = False
        self.unbind("<KeyPress>")
        self.unbind("<KeyRelease>")
        self._hotkey_var.set(self._settings.hotkey)
        self._hotkey_hint.config(text="Abgebrochen", foreground="red")
        self._record_btn.config(state="normal")
        self.after(2000, lambda: self._hotkey_hint.config(text=""))

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _open_log(self) -> None:
        import os
        log_path = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")), "Blitztext", "blitztext.log"
        )
        os.startfile(log_path)

    def _pick_and_transcribe_file(self) -> None:
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Audio-Datei auswählen",
            filetypes=[
                ("Audio-Dateien", "*.mp3 *.m4a *.wav *.ogg *.flac *.aac *.mp4 *.webm"),
                ("Alle Dateien", "*.*"),
            ],
        )
        if file_path and self._on_transcribe_file:
            self._on_transcribe_file(file_path)

    def _toggle_key_visibility(self) -> None:
        self._show_key = not self._show_key
        self._api_entry.config(show="" if self._show_key else "*")

    def _save(self) -> None:
        from blitztext import autostart, settings as settings_mod

        self._settings.hotkey = self._hotkey_var.get() or self._settings.hotkey
        self._settings.mode = self._mode_var.get()
        self._settings.polish_provider = self._polish_provider_var.get()
        self._settings.claude_api_key = self._api_key_var.get()
        self._settings.language = self._lang_var.get()
        self._settings.whisper_model = self._whisper_model_var.get()
        self._settings.whisper_device = self._whisper_device_var.get()
        self._settings.transcription_backend = self._backend_var.get()
        self._settings.openai_api_key = self._openai_key_var.get()
        self._settings.openai_transcribe_model = self._openai_model_var.get()
        self._settings.autostart = self._autostart_var.get()

        settings_mod.save(self._settings)

        if self._settings.autostart:
            autostart.enable()
        else:
            autostart.disable()

        needs_openai_key = (
            self._settings.transcription_backend == "openai"
            or (self._settings.mode != "direkt" and self._settings.polish_provider == "openai")
        )
        if needs_openai_key and not self._settings.openai_api_key:
            messagebox.showwarning(
                "Blitztext",
                "Kein OpenAI API Key eingetragen – die ausgewählte(n) OpenAI-Funktion(en) "
                "funktionieren erst, wenn einer eingetragen wird.\n\n"
                "Die Einstellungen wurden trotzdem gespeichert.",
            )

        self._on_save(self._settings)
        self.destroy()

    def _center(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def lift(self) -> None:
        self.attributes("-topmost", True)
        super().lift()
        self.after(200, lambda: self.attributes("-topmost", False))
