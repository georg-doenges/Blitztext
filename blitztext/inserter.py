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
import ctypes.wintypes as _wt
import time

import pyperclip

# Etwas warten, damit das Zielfenster den Fokus vollständig zurückbekommt
_FOCUS_DELAY = 0.12  # Sekunden

# ------------------------------------------------------------------
# Ctrl+V via SendInput (nur virtuelle Keys, kein Unicode-Char-Event)
# ------------------------------------------------------------------
_KEYEVENTF_KEYUP = 0x0002
_INPUT_KEYBOARD  = 1
_VK_CONTROL      = 0x11
_VK_V            = 0x56
_VK_BACK         = 0x08


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         _wt.WORD),
        ("wScan",       _wt.WORD),
        ("dwFlags",     _wt.DWORD),
        ("time",        _wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _MOUSEINPUT(ctypes.Structure):
    # Muss in der Union enthalten sein, damit sizeof(_INPUT) == 40 Bytes (64-bit Windows).
    # Windows verwirft SendInput lautlos, wenn cbSize falsch ist.
    _fields_ = [
        ("dx",          _wt.LONG),
        ("dy",          _wt.LONG),
        ("mouseData",   _wt.DWORD),
        ("dwFlags",     _wt.DWORD),
        ("time",        _wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]
    _anonymous_ = ("_u",)
    _fields_     = [("type", _wt.DWORD), ("_u", _U)]


def _send_ctrl_v() -> None:
    """Sendet Ctrl+V via SendInput – keine Unicode-Char-Nebeneffekte."""
    inputs = (_INPUT * 4)(
        _INPUT(type=_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_VK_CONTROL)),
        _INPUT(type=_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_VK_V)),
        _INPUT(type=_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_VK_V,       dwFlags=_KEYEVENTF_KEYUP)),
        _INPUT(type=_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_VK_CONTROL, dwFlags=_KEYEVENTF_KEYUP)),
    )
    ctypes.windll.user32.SendInput(4, inputs, ctypes.sizeof(_INPUT))


def _send_backspaces(count: int) -> None:
    """Sendet *count* Rücktaste-Anschläge via SendInput.

    Genutzt, um ein geschütztes Leerzeichen zu entfernen, das Windows/Office
    selbst einfügt, wenn der konfigurierte Hotkey die Leertaste enthält
    (Strg+Umschalt+Leertaste ist die native Windows/Office-Tastenkombination
    für ein geschütztes Leerzeichen – der Tastendruck erreicht neben pynputs
    Listener auch ganz normal das fokussierte Fenster). Über SendInput statt
    des alten pynput-Controllers, da Letzterer auf Windows jedes Tastenereignis
    doppelt sendet (Ursache des früheren Doppel-Einfüge-Bugs).
    """
    if count <= 0:
        return
    inputs = (_INPUT * (count * 2))()
    for i in range(count):
        inputs[i * 2]     = _INPUT(type=_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_VK_BACK))
        inputs[i * 2 + 1] = _INPUT(type=_INPUT_KEYBOARD, ki=_KEYBDINPUT(wVk=_VK_BACK, dwFlags=_KEYEVENTF_KEYUP))
    ctypes.windll.user32.SendInput(len(inputs), inputs, ctypes.sizeof(_INPUT))


def get_foreground_hwnd() -> int:
    """Gibt den HWND-Handle des aktuellen Vordergrund-Fensters zurück."""
    return ctypes.windll.user32.GetForegroundWindow()


def restore_focus(hwnd: int) -> None:
    """Stellt den Fokus auf das Fenster mit dem gegebenen HWND zurück.

    SetForegroundWindow allein scheitert in Hintergrundprozessen (Windows-Sperre).
    AttachThreadInput hängt unsere Input-Queue kurz an die des aktuellen
    Vordergrund-Threads, was die Sperre umgeht.
    """
    if not hwnd:
        return
    fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
    fg_tid  = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, None)
    cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    attached = False
    if fg_tid and fg_tid != cur_tid:
        ctypes.windll.user32.AttachThreadInput(cur_tid, fg_tid, True)
        attached = True
    ctypes.windll.user32.BringWindowToTop(hwnd)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    if attached:
        ctypes.windll.user32.AttachThreadInput(cur_tid, fg_tid, False)
    time.sleep(_FOCUS_DELAY)


def insert(text: str, hwnd: int = 0, delete_before: int = 0) -> None:
    """
    Fügt *text* an der aktuellen Cursor-Position ein.

    :param text: Der einzufügende Text.
    :param hwnd: HWND des Zielfensters (0 = kein expliziter Focus-Restore).
    :param delete_before: Anzahl Rücktaste-Anschläge vor dem Einfügen (entfernt
        geschützte Leerzeichen, die durch die Leertaste im Hotkey ins Zielfenster
        durchgerutscht sind, siehe _send_backspaces).
    """
    if not text:
        return

    # Fokus auf Ursprungsfenster zurück
    restore_focus(hwnd)

    # Vom Hotkey durchgerutschte geschützte Leerzeichen entfernen
    _send_backspaces(delete_before)

    # Text in Zwischenablage, kurz warten bis OS bereit
    pyperclip.copy(text)
    time.sleep(0.05)

    # Ctrl+V senden (via SendInput – kein pynput-Unicode-Nebeneffekt)
    _send_ctrl_v()
