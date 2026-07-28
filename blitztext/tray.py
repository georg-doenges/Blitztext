"""
TrayApp – System-Tray-Icon mit pystray.

Das Icon zeigt das Blitztext-Logo statisch (keine Farbwechsel je Zustand mehr –
Aufnahme/Verarbeitung werden bereits deutlich sichtbar über die Bildschirm-Badges
in overlay.py angezeigt, ein zusätzlicher Farbwechsel im Tray wäre redundant).

Menü und Tooltip-Text können thread-safe aktualisiert werden.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable, Optional

import pystray
from PIL import Image

from blitztext import overlay

if TYPE_CHECKING:
    from blitztext.settings import Settings

# Zustands-Konstanten
IDLE = "idle"
RECORDING = "recording"
PROCESSING = "processing"

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_TRAY_ICON_PATH = os.path.join(_ASSETS_DIR, "icon_tray.png")
_TRAY_ICON = Image.open(_TRAY_ICON_PATH)

_STATE_LABELS = {
    IDLE:       "Bereit",
    RECORDING:  "Nimmt auf …",
    PROCESSING: "Verarbeitet …",
}


def _show_about() -> None:
    import threading
    threading.Thread(target=_about_window, daemon=True, name="AboutDialog").start()


def _about_window() -> None:
    import tkinter as tk
    from tkinter import ttk
    import webbrowser
    from blitztext.version import __version__

    root = tk.Tk()
    root.title("Über Blitztext")
    root.resizable(False, False)

    pad = {"padx": 20, "pady": 6}
    ttk.Label(root, text="Blitztext", font=("Segoe UI", 16, "bold")).pack(**pad)
    ttk.Label(root, text=f"Version {__version__}").pack(pady=(0, 4))
    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=4)
    ttk.Label(root, text="Sprache-zu-Text für jede Windows-Anwendung").pack(**pad)
    ttk.Label(root, text="© 2026 Georg Dönges").pack(pady=(0, 4))

    link = ttk.Label(
        root,
        text="github.com/georg-doenges/Blitztext",
        foreground="#2563eb",
        cursor="hand2",
    )
    link.pack(pady=(0, 8))
    link.bind("<Button-1>", lambda _: webbrowser.open(
        "https://github.com/georg-doenges/Blitztext"
    ))

    ttk.Button(root, text="Schließen", command=root.destroy).pack(pady=(4, 16))

    # Zentrieren
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
    root.mainloop()


class TrayApp:
    def __init__(
        self,
        settings: "Settings",
        on_open_settings: Callable[[], None],
        on_toggle_mode: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._settings = settings
        self._on_open_settings = on_open_settings
        self._on_toggle_mode = on_toggle_mode
        self._on_quit = on_quit
        self._state = IDLE

        self._icon = pystray.Icon(
            name="Blitztext",
            icon=_TRAY_ICON,
            title="Blitztext – Bereit",
            menu=self._build_menu(),
        )

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Startet den Tray-Loop (blockiert, muss auf Main Thread aufgerufen werden)."""
        self._icon.run()

    def set_state(self, state: str) -> None:
        """Wechselt Tooltip-Text und Menü; thread-safe. Das Icon-Bild bleibt statisch
        (Status wird bereits über die Bildschirm-Badges in overlay.py angezeigt)."""
        self._state = state
        self._icon.title = f"Blitztext – {_STATE_LABELS[state]}"
        self._rebuild_menu()
        overlay.set_recording(state == RECORDING)
        overlay.set_processing(state == PROCESSING)

    def notify(self, title: str, message: str) -> None:
        """Zeigt eine Auto-Close-Benachrichtigung (schließt sich nach 4 s)."""
        overlay.notify(title, message)

    def update_settings(self, settings: "Settings") -> None:
        self._settings = settings
        self._rebuild_menu()

    def stop(self) -> None:
        self._icon.stop()

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        _mode_labels = {
            "direkt":              "Modus: Direkt  ✓",
            "poliert_konservativ": "Modus: Poliert – Konservativ  ✓",
            "poliert_ausgefeilt":  "Modus: Poliert – Ausgefeilt  ✓",
        }
        mode_label = _mode_labels.get(self._settings.mode, "Modus: Direkt  ✓")
        toggle_label = "zu Direkt wechseln" if self._settings.mode != "direkt" else "zu Poliert wechseln"
        state_item = pystray.MenuItem(
            f"Status: {_STATE_LABELS[self._state]}",
            None,
            enabled=False,
        )
        return pystray.Menu(
            state_item,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(mode_label, None, enabled=False),
            pystray.MenuItem(toggle_label, self._handle_toggle_mode),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Einstellungen …", self._handle_open_settings),
            pystray.MenuItem("Über Blitztext …", self._handle_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._handle_quit),
        )

    def _rebuild_menu(self) -> None:
        self._icon.menu = self._build_menu()

    def _handle_open_settings(self, icon, item) -> None:
        self._on_open_settings()

    def _handle_toggle_mode(self, icon, item) -> None:
        self._on_toggle_mode()

    def _handle_about(self, icon, item) -> None:
        _show_about()

    def _handle_quit(self, icon, item) -> None:
        self._on_quit()
