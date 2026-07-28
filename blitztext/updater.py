"""
Updater – prüft beim Start ob eine neuere Version auf GitHub verfügbar ist.
Führt git pull im Hintergrund aus; benachrichtigt den Nutzer bei Änderungen.

Enthält zusätzlich check_remote_version()/apply_update() für die manuelle
Update-Prüfung über den Button im Einstellungsfenster. Bewusst KEIN "pip install"
während Blitztext läuft: Windows sperrt geladene .pyd/.dll-Dateien laufender
Prozesse, ein Überschreiben schlägt dann fehl (Ursache mehrfacher venv-Schäden
in der Vergangenheit). Wenn sich requirements.txt ändert, wird stattdessen auf
eine erneute Ausführung von install.ps1 verwiesen (nach manuellem Beenden).
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from typing import Callable, Optional, Tuple

log = logging.getLogger(__name__)

_REMOTE = "origin"
_BRANCH = "main"
_INSTALL_CMD = "irm https://raw.githubusercontent.com/georg-doenges/Blitztext/main/install.ps1 | iex"


def check_for_updates(
    install_dir: str,
    on_update_found: Callable[[str], None],
) -> None:
    """Startet git pull im Hintergrund. Nicht-blockierend."""
    t = threading.Thread(
        target=_pull,
        args=(install_dir, on_update_found),
        daemon=True,
        name="Updater",
    )
    t.start()


def _pull(install_dir: str, on_update_found: Callable[[str], None]) -> None:
    if not os.path.isdir(os.path.join(install_dir, ".git")):
        log.debug("Kein git-Repository in %s – Update übersprungen", install_dir)
        return
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=install_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        log.info("git pull: %s", output)
        if result.returncode == 0 and "Already up to date" not in output:
            on_update_found(
                "Blitztext wurde aktualisiert.\n"
                "Bitte Blitztext neu starten, um die neue Version zu verwenden."
            )
    except FileNotFoundError:
        log.debug("git nicht gefunden – kein Auto-Update möglich")
    except subprocess.TimeoutExpired:
        log.warning("git pull Timeout – Update übersprungen")
    except Exception as e:
        log.warning("Auto-Update fehlgeschlagen: %s", e)


# ---------------------------------------------------------------------------
# Manuelle Update-Prüfung (Button im Einstellungsfenster)
# ---------------------------------------------------------------------------

def check_remote_version(install_dir: str) -> Tuple[str, str]:
    """
    Fragt GitHub ab, ob eine neuere Version vorliegt. Rein lesend (git fetch),
    verändert nichts an der Installation.

    Returns (status, detail):
      status: "update_available" | "up_to_date" | "error" | "no_repo"
    """
    if not os.path.isdir(os.path.join(install_dir, ".git")):
        return "no_repo", "Kein Git-Repository gefunden – Update-Prüfung nicht möglich."
    try:
        fetch = subprocess.run(
            ["git", "fetch", _REMOTE, _BRANCH, "--quiet"],
            cwd=install_dir, capture_output=True, text=True, timeout=30,
        )
        if fetch.returncode != 0:
            return "error", f"Verbindung zu GitHub fehlgeschlagen:\n{fetch.stderr.strip()}"

        ahead = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..{_REMOTE}/{_BRANCH}"],
            cwd=install_dir, capture_output=True, text=True, timeout=15,
        )
        count = int(ahead.stdout.strip() or "0")
        if count == 0:
            from blitztext.version import __version__
            return "up_to_date", f"Blitztext ist aktuell (Version {__version__})."

        is_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "HEAD", f"{_REMOTE}/{_BRANCH}"],
            cwd=install_dir, capture_output=True, text=True, timeout=15,
        )
        if is_ancestor.returncode != 0:
            return "error", (
                "Die lokale Installation weicht vom GitHub-Stand ab – ein automatisches "
                "Update ist nicht möglich."
            )

        remote_version = _read_remote_version(install_dir)
        detail = f"{count} neue Änderung(en) verfügbar"
        if remote_version:
            detail += f" (Version {remote_version})"
        detail += "."
        return "update_available", detail
    except subprocess.TimeoutExpired:
        return "error", "Zeitüberschreitung bei der Update-Prüfung."
    except FileNotFoundError:
        return "error", "Git wurde nicht gefunden."
    except Exception as e:
        return "error", f"Update-Prüfung fehlgeschlagen: {e}"


def _read_remote_version(install_dir: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "show", f"{_REMOTE}/{_BRANCH}:blitztext/version.py"],
            cwd=install_dir, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        match = re.search(r'__version__\s*=\s*"([^"]+)"', result.stdout)
        return match.group(1) if match else None
    except Exception:
        return None


def apply_update(install_dir: str) -> Tuple[str, str]:
    """
    Lädt den neuesten Code per 'git pull --ff-only' (unkritisch – Python-Quelldateien
    werden von Windows nicht wie geladene .pyd/.dll gesperrt, das passiert schon heute
    beim automatischen Start-Update ohne Probleme).

    Führt bewusst KEIN 'pip install' aus. Falls sich requirements.txt geändert hat,
    wird stattdessen auf die manuelle Installer-Ausführung verwiesen.

    Returns (status, message): status in "updated" | "needs_manual_reinstall" | "error"
    """
    try:
        old_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=install_dir,
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()

        pull = subprocess.run(
            ["git", "pull", "--ff-only"], cwd=install_dir,
            capture_output=True, text=True, timeout=60,
        )
        if pull.returncode != 0:
            return "error", f"Update fehlgeschlagen:\n{pull.stderr.strip() or pull.stdout.strip()}"

        new_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=install_dir,
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()

        diff = subprocess.run(
            ["git", "diff", "--name-only", old_head, new_head],
            cwd=install_dir, capture_output=True, text=True, timeout=15,
        )
        changed_files = diff.stdout.strip().splitlines()

        if "requirements.txt" in changed_files:
            return "needs_manual_reinstall", (
                "Der Code wurde aktualisiert. Diese Version benötigt aber auch neue oder "
                "geänderte Programmbibliotheken – die können aus Sicherheitsgründen nicht "
                "automatisch installiert werden, solange Blitztext läuft.\n\n"
                "Bitte so vorgehen:\n"
                "1. Blitztext beenden (Rechtsklick auf das Tray-Symbol → Beenden)\n"
                "2. PowerShell öffnen\n"
                f"3. Diesen Befehl ausführen:\n{_INSTALL_CMD}"
            )
        return "updated", (
            "Blitztext wurde aktualisiert.\n\n"
            "Bitte einmal neu starten: Tray-Symbol → Beenden, dann die Verknüpfung "
            "erneut öffnen."
        )
    except subprocess.TimeoutExpired:
        return "error", "Zeitüberschreitung beim Update."
    except FileNotFoundError:
        return "error", "Git wurde nicht gefunden."
    except Exception as e:
        return "error", f"Update-Fehler: {e}"
