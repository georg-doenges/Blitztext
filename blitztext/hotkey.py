"""
HotkeyManager – registriert einen globalen Hotkey via pynput (kein Admin nötig).

Der Hotkey toggelt zwischen IDLE→RECORDING und RECORDING→PROCESSING.
Bei Konfigurationsänderung kann der Listener gestoppt und neu gestartet werden.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from pynput import keyboard as pynput_kb

# Mapping von lesbaren Kurzschreibweisen auf pynput-Key-Objekte
_SPECIAL_KEYS = {
    "ctrl":  pynput_kb.Key.ctrl,
    "shift": pynput_kb.Key.shift,
    "alt":   pynput_kb.Key.alt,
    "space": pynput_kb.Key.space,
    "tab":   pynput_kb.Key.tab,
    "enter": pynput_kb.Key.enter,
}


def _parse_hotkey(hotkey_str: str) -> str:
    """
    Wandelt 'ctrl+shift+space' in das pynput-Format '<ctrl>+<shift>+<space>' um.
    Einzelne Zeichen (a-z, 0-9) bleiben unverändert.
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    pynput_parts = []
    for part in parts:
        if part in _SPECIAL_KEYS:
            pynput_parts.append(f"<{part}>")
        else:
            pynput_parts.append(part)
    return "+".join(pynput_parts)


class HotkeyManager:
    def __init__(self, hotkey_str: str, on_activate: Callable[[], None]) -> None:
        """
        :param hotkey_str: z.B. "ctrl+shift+space"
        :param on_activate: Wird bei jedem Hotkey-Druck aufgerufen (auf Hotkey-Thread).
        """
        self._hotkey_str = hotkey_str
        self._on_activate = on_activate
        self._listener: Optional[pynput_kb.GlobalHotKeys] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Startet den Listener. Threadsafe."""
        with self._lock:
            self._start_listener()

    def stop(self) -> None:
        """Stoppt den Listener. Threadsafe."""
        with self._lock:
            self._stop_listener()

    def update_hotkey(self, new_hotkey_str: str) -> None:
        """Stoppt den alten Listener und startet einen neuen mit dem neuen Hotkey."""
        with self._lock:
            self._hotkey_str = new_hotkey_str
            self._stop_listener()
            self._start_listener()

    # ------------------------------------------------------------------
    # Intern (muss unter self._lock aufgerufen werden)
    # ------------------------------------------------------------------

    def _start_listener(self) -> None:
        pynput_hotkey = _parse_hotkey(self._hotkey_str)
        self._listener = pynput_kb.GlobalHotKeys(
            {pynput_hotkey: self._on_activate}
        )
        self._listener.start()

    def _stop_listener(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
