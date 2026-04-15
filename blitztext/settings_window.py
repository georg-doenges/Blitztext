"""
SettingsWindow – tkinter-Einstellungsfenster.

Läuft in einem eigenen Thread (tkinter ist nicht thread-safe).
Singleton-Guard verhindert mehrere gleichzeitig offene Fenster.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from blitztext.settings import Settings

_window_thread: Optional[threading.Thread] = None
_window_instance: Optional["SettingsWindow"] = None
_lock = threading.Lock()


def open_settings(
    settings: "Settings",
    on_save: Callable[["Settings"], None],
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
            args=(settings, on_save),
            daemon=True,
            name="SettingsWindow",
        )
        _window_thread.start()


def _run_window(settings: "Settings", on_save: Callable[["Settings"], None]) -> None:
    global _window_instance
    import gc
    win = SettingsWindow(settings, on_save)
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
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_save = on_save
        self._capturing_hotkey = False

        self.title("Blitztext – Einstellungen")
        self.resizable(False, False)
        self._build_ui()
        self._center()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # --- Hotkey ---
        ttk.Label(self, text="Tastenkombination:").grid(
            row=0, column=0, sticky="w", **pad
        )
        self._hotkey_var = tk.StringVar(value=self._settings.hotkey)
        self._hotkey_entry = ttk.Entry(
            self, textvariable=self._hotkey_var, width=24, state="readonly"
        )
        self._hotkey_entry.grid(row=0, column=1, sticky="ew", **pad)
        self._record_btn = ttk.Button(
            self, text="Aufnehmen", command=self._start_hotkey_capture
        )
        self._record_btn.grid(row=0, column=2, **pad)

        # Hinweis-Label für Hotkey-Aufnahme
        self._hotkey_hint = ttk.Label(self, text="", foreground="gray")
        self._hotkey_hint.grid(row=1, column=0, columnspan=3, **pad)

        # --- Modus ---
        ttk.Label(self, text="Modus:").grid(row=2, column=0, sticky="w", **pad)
        self._mode_var = tk.StringVar(value=self._settings.mode)
        mode_frame = ttk.Frame(self)
        mode_frame.grid(row=2, column=1, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(
            mode_frame, text="Direkt", variable=self._mode_var, value="direkt"
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            mode_frame, text="Poliert (Claude)", variable=self._mode_var, value="poliert"
        ).pack(side="left", padx=4)

        # --- Claude API Key ---
        ttk.Label(self, text="Claude API Key:").grid(row=3, column=0, sticky="w", **pad)
        self._api_key_var = tk.StringVar(value=self._settings.claude_api_key)
        self._api_entry = ttk.Entry(
            self, textvariable=self._api_key_var, show="*", width=32
        )
        self._api_entry.grid(row=3, column=1, sticky="ew", **pad)
        self._show_key = False
        ttk.Button(self, text="Anzeigen", command=self._toggle_key_visibility).grid(
            row=3, column=2, **pad
        )

        # --- Sprache ---
        ttk.Label(self, text="Sprache (Whisper):").grid(
            row=4, column=0, sticky="w", **pad
        )
        self._lang_var = tk.StringVar(value=self._settings.language)
        lang_cb = ttk.Combobox(
            self,
            textvariable=self._lang_var,
            values=["de", "en", "fr", "es", "it", ""],
            width=8,
            state="readonly",
        )
        lang_cb.grid(row=4, column=1, sticky="w", **pad)
        ttk.Label(self, text='(leer = auto)', foreground="gray").grid(
            row=4, column=2, sticky="w"
        )

        # --- Autostart ---
        from blitztext import autostart
        self._autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(
            self, text="Mit Windows starten", variable=self._autostart_var
        ).grid(row=5, column=0, columnspan=3, sticky="w", **pad)

        # --- Log anzeigen ---
        ttk.Button(
            self, text="Log anzeigen", command=self._open_log
        ).grid(row=6, column=0, columnspan=3, sticky="w", **pad)

        # --- Buttons ---
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=7, column=0, columnspan=3, pady=12)
        ttk.Button(btn_frame, text="Speichern", command=self._save).pack(
            side="left", padx=8
        )
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(
            side="left", padx=8
        )

        self.columnconfigure(1, weight=1)

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

    def _toggle_key_visibility(self) -> None:
        self._show_key = not self._show_key
        self._api_entry.config(show="" if self._show_key else "*")

    def _save(self) -> None:
        from blitztext import autostart, settings as settings_mod

        self._settings.hotkey = self._hotkey_var.get() or self._settings.hotkey
        self._settings.mode = self._mode_var.get()
        self._settings.claude_api_key = self._api_key_var.get()
        self._settings.language = self._lang_var.get()
        self._settings.autostart = self._autostart_var.get()

        settings_mod.save(self._settings)

        if self._settings.autostart:
            autostart.enable()
        else:
            autostart.disable()

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
