"""
Updater – prüft beim Start ob eine neuere Version auf GitHub verfügbar ist.
Führt git pull im Hintergrund aus; benachrichtigt den Nutzer bei Änderungen.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Callable

log = logging.getLogger(__name__)


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
