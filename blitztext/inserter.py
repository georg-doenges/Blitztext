"""
TextInserter – fügt Text an der aktuellen Cursor-Position ein.

Strategie: Text in Zwischenablage kopieren, dann Ctrl+V simulieren.
Das funktioniert mit allen Unicode-Zeichen (inkl. deutscher Umlaute) und
in praktisch allen Windows-Applikationen.

Focus-Restore: Das HWND-Handle des Vordergrund-Fensters vor der Aufnahme
wird übergeben und vor dem Einfügen wiederhergestellt.
"""
from __future__ import annotations

import ctypes
import time

import pyperclip
from pynput.keyboard import Controller, Key

_keyboard_ctrl = Controller()

# Etwas warten, damit das Zielfenster den Fokus vollständig zurückbekommt
_FOCUS_DELAY = 0.12  # Sekunden


def get_foreground_hwnd() -> int:
    """Gibt den HWND-Handle des aktuellen Vordergrund-Fensters zurück."""
    return ctypes.windll.user32.GetForegroundWindow()


def restore_focus(hwnd: int) -> None:
    """Stellt den Fokus auf das Fenster mit dem gegebenen HWND zurück."""
    if hwnd:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(_FOCUS_DELAY)


def insert(text: str, hwnd: int = 0, delete_before: int = 0) -> None:
    """
    Fügt *text* an der aktuellen Cursor-Position ein.

    :param text: Der einzufügende Text.
    :param hwnd: HWND des Zielfensters (0 = kein expliziter Focus-Restore).
    :param delete_before: Anzahl Backspaces, die vor dem Einfügen gesendet werden
                          (zum Entfernen von Leerzeichen, die durch den Hotkey eingetippt wurden).
    """
    if not text:
        return

    # Fokus auf Ursprungsfenster zurück
    restore_focus(hwnd)

    # Vom Hotkey durchgerutschte Leerzeichen entfernen
    for _ in range(delete_before):
        _keyboard_ctrl.press(Key.backspace)
        _keyboard_ctrl.release(Key.backspace)

    # Text in Zwischenablage
    pyperclip.copy(text)

    # Ctrl+V senden
    with _keyboard_ctrl.pressed(Key.ctrl):
        _keyboard_ctrl.press("v")
        _keyboard_ctrl.release("v")
