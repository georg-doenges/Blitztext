"""
AutostartManager – trägt Blitztext in den Windows-Autostart ein (HKCU, kein Admin nötig).
"""
from __future__ import annotations

import sys
import os
import winreg

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "Blitztext"

# Frühere Autostart-Methode (Installer legte eine Verknüpfung hier ab).
# Wird nicht mehr neu angelegt, aber bei enable()/disable() bereinigt, damit
# Bestandsinstallationen nicht zwei unabhängige Autostart-Wege gleichzeitig
# haben (Checkbox in den Einstellungen steuerte bisher nur die Registry,
# während die Verknüpfung unabhängig davon weiter startete).
_STARTUP_LNK = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Blitztext.lnk",
)


def _run_value(script_path: str | None = None) -> str:
    """Gibt den Wert zurück, der in die Registry eingetragen wird."""
    script = os.path.abspath(script_path or sys.argv[0])
    # pythonw.exe startet ohne Konsolenfenster
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{script}"'


def _remove_legacy_shortcut() -> None:
    try:
        if os.path.exists(_STARTUP_LNK):
            os.remove(_STARTUP_LNK)
    except OSError:
        pass


def enable(script_path: str | None = None) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _run_value(script_path))
    _remove_legacy_shortcut()


def disable() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _APP_NAME)
    except FileNotFoundError:
        pass
    _remove_legacy_shortcut()


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except FileNotFoundError:
        pass
    # Bestandsinstallation mit alter Verknüpfungsmethode, Registry noch nie gesetzt
    return os.path.exists(_STARTUP_LNK)
