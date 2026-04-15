"""
TrayApp – System-Tray-Icon mit pystray.

Drei Zustände mit farblich unterschiedlichen Icons (programmatisch mit Pillow):
  IDLE       – grau   (Bereit)
  RECORDING  – rot    (Nimmt auf)
  PROCESSING – blau   (Transkribiert / sendet an Claude)

Das Icon und das Menü können thread-safe aktualisiert werden.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

import pystray
from PIL import Image, ImageDraw

from blitztext import overlay

if TYPE_CHECKING:
    from blitztext.settings import Settings

# Zustands-Konstanten
IDLE = "idle"
RECORDING = "recording"
PROCESSING = "processing"

_ICON_SIZE = 64
_COLORS = {
    IDLE:       ("#6b7280", "#9ca3af"),   # grau (Kreis, Mikrofon)
    RECORDING:  ("#dc2626", "#f87171"),   # rot
    PROCESSING: ("#2563eb", "#60a5fa"),   # blau
}


def _make_icon(state: str) -> Image.Image:
    """Erstellt ein 64×64 Icon für den gegebenen Zustand."""
    bg_color, mic_color = _COLORS[state]
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Hintergrundkreis
    margin = 4
    draw.ellipse(
        [margin, margin, _ICON_SIZE - margin, _ICON_SIZE - margin],
        fill=bg_color,
    )

    # Einfaches Mikrofon-Symbol
    cx = _ICON_SIZE // 2
    # Mikrofon-Körper (abgerundetes Rechteck)
    mic_w, mic_h = 14, 20
    mic_top = 10
    draw.rounded_rectangle(
        [cx - mic_w // 2, mic_top, cx + mic_w // 2, mic_top + mic_h],
        radius=7,
        fill=mic_color,
    )
    # Mikrofon-Bogen (U-Form)
    arc_r = 16
    arc_y = mic_top + mic_h - arc_r + 4
    draw.arc(
        [cx - arc_r, arc_y, cx + arc_r, arc_y + arc_r * 2],
        start=0, end=180,
        fill=mic_color,
        width=3,
    )
    # Stiel
    draw.line([cx, arc_y + arc_r, cx, arc_y + arc_r + 8], fill=mic_color, width=3)
    draw.line(
        [cx - 8, arc_y + arc_r + 8, cx + 8, arc_y + arc_r + 8],
        fill=mic_color,
        width=3,
    )

    return img


_ICONS = {state: _make_icon(state) for state in (IDLE, RECORDING, PROCESSING)}

_STATE_LABELS = {
    IDLE:       "Bereit",
    RECORDING:  "Nimmt auf …",
    PROCESSING: "Verarbeitet …",
}


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
            icon=_ICONS[IDLE],
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
        """Wechselt Icon und Tooltip; thread-safe."""
        self._state = state
        self._icon.icon = _ICONS[state]
        self._icon.title = f"Blitztext – {_STATE_LABELS[state]}"
        self._rebuild_menu()
        overlay.set_recording(state == RECORDING)

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
        toggle_label = "→ Direkt wechseln" if self._settings.mode != "direkt" else "→ Poliert wechseln"
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
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._handle_quit),
        )

    def _rebuild_menu(self) -> None:
        self._icon.menu = self._build_menu()

    def _handle_open_settings(self, icon, item) -> None:
        self._on_open_settings()

    def _handle_toggle_mode(self, icon, item) -> None:
        self._on_toggle_mode()

    def _handle_quit(self, icon, item) -> None:
        self._on_quit()
