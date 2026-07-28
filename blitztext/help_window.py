"""
help_window.py – In-App-Hilfe für Blitztext, aufrufbar über den "Hilfe"-Button
im Einstellungsfenster.

Gliederung in Tabs (ttk.Notebook), damit Nutzer nur die Themen lesen, die sie
gerade interessieren, statt einen langen Fließtext durchzuscrollen. Als
Toplevel des Einstellungsfensters implementiert (kein eigener Thread nötig,
tkinter erlaubt mehrere Toplevels auf demselben Thread).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from blitztext.settings import Settings

_KEY_LABELS = {
    "ctrl": "Strg", "shift": "Umschalt", "alt": "Alt",
    "space": "Leertaste", "tab": "Tab", "enter": "Eingabe",
    "minus": "Minus", "underscore": "Unterstrich", "equal": "Gleich",
}


def format_hotkey(hotkey_str: str) -> str:
    """Wandelt z.B. 'ctrl+shift+space' in 'Strg + Umschalt + Leertaste' um."""
    parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
    return " + ".join(_KEY_LABELS.get(p, p.upper()) for p in parts)


def _build_tabs(settings: "Settings") -> List[Tuple[str, List[Tuple[str, str]]]]:
    record_key = format_hotkey(settings.hotkey)
    settings_key = format_hotkey(settings.settings_hotkey)

    return [
        ("Schnellstart", [
            ("So funktioniert's", (
                f"1. Klicke in das Textfeld, in das der Text eingefügt werden soll "
                f"(z. B. Word, Outlook, ein Browser-Formular).\n"
                f"2. Drücke {record_key} – die Aufnahme startet.\n"
                f"3. Sprich.\n"
                f"4. Drücke {record_key} erneut – die Aufnahme stoppt, der Text "
                f"erscheint automatisch dort, wo der Cursor steht."
            )),
            ("Einstellungen öffnen", (
                f"Per Tastenkombination {settings_key}, oder per Rechtsklick auf das "
                f"Blitztext-Symbol unten rechts neben der Uhr → „Einstellungen …“."
            )),
            ("Status erkennen", (
                "Während der Aufnahme erscheint unten rechts ein rotes „● REC“-Feld, "
                "während der Verarbeitung ein blaues „● Processing“-Feld. Beide "
                "verschwinden von selbst, sobald der Schritt fertig ist."
            )),
            ("Modus schnell wechseln", (
                "Rechtsklick auf das Tray-Symbol → „zu Poliert wechseln“ schaltet "
                "zwischen Direkt und Poliert – Konservativ um, ohne die Einstellungen "
                "zu öffnen."
            )),
        ]),
        ("Spracherkennung", [
            ("Lokal (Standard)", (
                "Whisper läuft direkt auf diesem Rechner – komplett offline, keine "
                "Kosten, keine Daten verlassen den PC. Mit einer NVIDIA-Grafikkarte ist "
                "ein größeres Modell in wenigen Sekunden fertig; ohne GPU empfiehlt "
                "sich ein kleineres Modell für akzeptable Geschwindigkeit."
            )),
            ("OpenAI-Cloud (optional)", (
                "Die Aufnahme wird zur Transkription an OpenAI geschickt – deutlich "
                "genauer als ein kleines lokales Modell auf der CPU, aber die Aufnahme "
                "verlässt dabei den Rechner, und es entstehen geringe Kosten (ca. "
                "0,003–0,006 USD pro Minute). Erfordert einen OpenAI API Key, dafür "
                "kein Modell-Download."
            )),
            ("Wo einstellen", (
                "Einstellungen → Bereich „Spracherkennung“. Ein Wechsel des Backends "
                "wird erst nach einem Neustart von Blitztext aktiv."
            )),
        ]),
        ("Textveredelung", [
            ("Direkt (Standard)", (
                "Der erkannte Text wird unverändert eingefügt. Schnell, funktioniert "
                "komplett offline ohne Internet."
            )),
            ("Poliert – Konservativ", (
                "Entfernt Füllwörter („ähm“, „also“, „sozusagen“) und korrigiert "
                "offensichtliche Grammatikfehler. Dein Stil und deine Wortwahl bleiben "
                "erhalten."
            )),
            ("Poliert – Ausgefeilt", (
                "Vollständige Überarbeitung: saubere Formulierungen, korrekte "
                "Zeichensetzung, sinnvolle Absätze. E-Mails werden automatisch mit "
                "Anrede, Fließtext und Grußzeile formatiert."
            )),
            ("Anbieter wählen", (
                "Für beide Poliert-Modi kannst du zwischen Claude und OpenAI wählen "
                "(Einstellungen → „Textveredelung“). Beide benötigen einen eigenen "
                "API Key."
            )),
        ]),
        ("API Keys", [
            ("Claude (Anthropic)", (
                "console.anthropic.com öffnen → Konto erstellen → API Key erstellen → "
                "in den Einstellungen eintragen. Nötig für die Poliert-Modi mit "
                "Anbieter „Claude“."
            )),
            ("OpenAI", (
                "platform.openai.com öffnen → Konto erstellen → API Key unter „API "
                "keys“ erstellen → in den Einstellungen eintragen. Ein einziger Key "
                "reicht für beide OpenAI-Funktionen (Cloud-Spracherkennung und "
                "Textveredelung mit Anbieter „OpenAI“)."
            )),
            ("Sicherheitshinweis", (
                "Beide Keys werden unverschlüsselt in "
                "%APPDATA%\\Blitztext\\settings.json gespeichert – für ein persönlich "
                "genutztes Gerät unkritisch, auf einem gemeinsam genutzten Rechner "
                "sollte niemand sonst Zugriff auf dieses Benutzerkonto haben."
            )),
        ]),
        ("Sonstiges", [
            ("Automatisch starten", (
                "Häkchen „Mit Windows starten“ im Bereich „System“ der Einstellungen."
            )),
            ("Nach Updates suchen", (
                "Button „Nach Updates suchen …“ im Bereich „System“ prüft, ob eine "
                "neuere Version auf GitHub verfügbar ist, und führt dich durch die "
                "Installation."
            )),
            ("Log ansehen", (
                "Button „Log anzeigen“ öffnet die Log-Datei – hilfreich, falls etwas "
                "nicht wie erwartet funktioniert."
            )),
            ("Text wird nicht eingefügt", (
                "Klicke einmal in das Zielfeld, bevor du den Hotkey drückst, damit das "
                "richtige Fenster aktiv ist."
            )),
            ("Tray-Symbol nicht sichtbar", (
                "Klicke auf den kleinen Pfeil „^“ neben der Uhr – das Symbol kann dort "
                "versteckt sein. Per Drag & Drop lässt es sich dauerhaft sichtbar "
                "machen."
            )),
        ]),
    ]


def open_help(parent: tk.Misc, settings: "Settings") -> None:
    """Öffnet das Hilfefenster als Toplevel von *parent* (typischerweise das
    Einstellungsfenster)."""
    win = tk.Toplevel(parent)
    win.title("Blitztext – Hilfe")
    win.geometry("580x480")
    win.transient(parent)

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=10, pady=(10, 4))

    for title, blocks in _build_tabs(settings):
        _add_tab(notebook, title, blocks)

    ttk.Button(win, text="Schließen", command=win.destroy).pack(pady=(0, 10))

    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
    win.lift()
    win.focus_force()


def _add_tab(notebook: ttk.Notebook, title: str, blocks: List[Tuple[str, str]]) -> None:
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=title)

    text_widget = tk.Text(
        frame, wrap="word", relief="flat", padx=14, pady=12,
        font=("Segoe UI", 10), borderwidth=0, cursor="arrow",
    )
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=scrollbar.set)
    text_widget.tag_configure("heading", font=("Segoe UI", 10, "bold"), spacing3=4)
    text_widget.tag_configure("body", font=("Segoe UI", 10), spacing3=14)

    for heading, body in blocks:
        text_widget.insert("end", heading + "\n", "heading")
        text_widget.insert("end", body + "\n", "body")

    text_widget.configure(state="disabled")
    text_widget.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
