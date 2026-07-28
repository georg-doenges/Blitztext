"""
HotkeyManager – registriert einen oder mehrere globale Hotkeys via pynput (kein Admin nötig).

Jeder Hotkey ist unter einem logischen Namen registriert (z.B. "record", "settings")
und kann einzeln neu zugewiesen werden. Bei Konfigurationsänderung wird der komplette
Listener gestoppt und mit der aktuellen Zuordnung neu gestartet (pynput erlaubt keine
Änderung einer laufenden GlobalHotKeys-Instanz).
"""
from __future__ import annotations

import threading
from typing import Callable, Dict, Optional, Tuple

from pynput import keyboard as pynput_kb

# Mapping von lesbaren Kurzschreibweisen auf pynput-Key-Objekte (Tasten ohne eigenes
# druckbares Zeichen, z.B. Modifier oder Leertaste).
_SPECIAL_KEYS = {
    "ctrl":  pynput_kb.Key.ctrl,
    "shift": pynput_kb.Key.shift,
    "alt":   pynput_kb.Key.alt,
    "space": pynput_kb.Key.space,
    "tab":   pynput_kb.Key.tab,
    "enter": pynput_kb.Key.enter,
}

# Tkinter liefert für Satzzeichen-Tasten Wortnamen (keysym) statt des Zeichens selbst
# (z.B. "minus" statt "-"). pynput erwartet dagegen das tatsächliche Zeichen.
_CHAR_ALIASES = {
    "minus": "-", "underscore": "_", "equal": "=", "plus": "+",
    "comma": ",", "period": ".", "slash": "/", "backslash": "\\",
    "semicolon": ";", "apostrophe": "'", "grave": "`",
    "bracketleft": "[", "bracketright": "]",
}


def _parse_hotkey(hotkey_str: str) -> str:
    """
    Wandelt 'ctrl+shift+space' in das pynput-Format '<ctrl>+<shift>+<space>' um.
    Einzelne Zeichen (a-z, 0-9) bleiben unverändert; bekannte Satzzeichen-Namen
    werden über _CHAR_ALIASES auf ihr tatsächliches Zeichen abgebildet.
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    pynput_parts = []
    for part in parts:
        if part in _SPECIAL_KEYS:
            pynput_parts.append(f"<{part}>")
        else:
            pynput_parts.append(_CHAR_ALIASES.get(part, part))
    return "+".join(pynput_parts)


class HotkeyManager:
    def __init__(self, bindings: Dict[str, Tuple[str, Callable[[], None]]]) -> None:
        """
        :param bindings: {logischer_name: (hotkey_str, callback)}, z.B.
            {"record": ("ctrl+shift+space", self._on_hotkey),
             "settings": ("ctrl+shift+minus", self._open_settings)}
        """
        self._bindings: Dict[str, Tuple[str, Callable[[], None]]] = dict(bindings)
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

    def update_hotkey(self, name: str, new_hotkey_str: str) -> None:
        """Ändert den Hotkey-String für einen einzelnen Namen und startet den Listener neu."""
        with self._lock:
            old_str, callback = self._bindings[name]
            self._bindings[name] = (new_hotkey_str, callback)
            self._stop_listener()
            self._start_listener()

    # ------------------------------------------------------------------
    # Intern (muss unter self._lock aufgerufen werden)
    # ------------------------------------------------------------------

    def _start_listener(self) -> None:
        mapping = {
            _parse_hotkey(hotkey_str): callback
            for hotkey_str, callback in self._bindings.values()
        }
        self._listener = pynput_kb.GlobalHotKeys(mapping)
        self._listener.start()

    def _stop_listener(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
