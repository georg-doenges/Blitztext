"""
overlay.py – Floating REC-Indikator und Auto-Close-Benachrichtigungen.

Läuft in einem eigenen Thread mit eigenem tkinter-Root.
Kommunikation über eine Queue (thread-safe, kann von beliebigem Thread aufgerufen werden).

Zwei visuelle Elemente:
  - REC-Badge:      kleines rotes "● REC"-Fenster (erscheint nur während Aufnahme)
  - Notification:   dunkles Popup unten rechts, schließt sich automatisch nach 4 s
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Optional

_q: queue.Queue = queue.Queue()
_thread: Optional[threading.Thread] = None

_TASKBAR_H = 52   # Typische Taskbar-Höhe (px)
_MARGIN    = 12   # Abstand vom Bildschirmrand


# -----------------------------------------------------------------------
# Öffentliche API (thread-safe)
# -----------------------------------------------------------------------

def start() -> None:
    """Startet den Overlay-Thread. Einmal beim App-Start aufrufen."""
    global _thread
    _thread = threading.Thread(target=_run, daemon=True, name="Overlay")
    _thread.start()


def set_recording(active: bool) -> None:
    """REC-Badge ein- oder ausblenden."""
    _q.put(("rec", active))


def notify(title: str, message: str) -> None:
    """Benachrichtigung anzeigen (schließt sich nach 4 s automatisch)."""
    _q.put(("notify", title, message))


# -----------------------------------------------------------------------
# Intern – alles ab hier läuft nur auf dem Overlay-Thread
# -----------------------------------------------------------------------

def _run() -> None:
    root = tk.Tk()
    root.withdraw()  # Root-Fenster unsichtbar halten

    # --- REC-Badge ---
    rec = tk.Toplevel(root)
    rec.withdraw()
    rec.overrideredirect(True)       # Keine Titelleiste
    rec.attributes("-topmost", True)
    rec.attributes("-alpha", 0.88)
    rec.configure(bg="#dc2626")
    try:
        rec.wm_attributes("-toolwindow", True)  # Kein Taskbar-Eintrag (Windows)
    except tk.TclError:
        pass

    tk.Label(
        rec, text="  ● REC  ",
        bg="#dc2626", fg="white",
        font=("Segoe UI", 10, "bold"),
        padx=4, pady=4,
    ).pack()

    def _show_rec() -> None:
        rec.update_idletasks()
        sw = rec.winfo_screenwidth()
        sh = rec.winfo_screenheight()
        w  = rec.winfo_reqwidth()
        h  = rec.winfo_reqheight()
        rec.geometry(f"+{sw - w - _MARGIN}+{sh - h - _TASKBAR_H - _MARGIN}")
        rec.deiconify()
        rec.lift()

    # --- Benachrichtigungs-Popup ---
    def _show_notification(title: str, message: str) -> None:
        win = tk.Toplevel(root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.93)
        win.configure(bg="#1f2937")
        try:
            win.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass

        tk.Label(
            win, text=title,
            bg="#1f2937", fg="white",
            font=("Segoe UI", 9, "bold"),
            anchor="w", padx=12, pady=6,
        ).pack(fill="x")
        tk.Label(
            win, text=message,
            bg="#1f2937", fg="#d1d5db",
            font=("Segoe UI", 9),
            anchor="w", padx=12, pady=0,
            wraplength=270, justify="left",
        ).pack(fill="x", pady=(0, 8))

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w  = win.winfo_reqwidth()
        h  = win.winfo_reqheight()
        # Oberhalb des REC-Badges positionieren
        win.geometry(f"+{sw - w - _MARGIN}+{sh - h - _TASKBAR_H - 50 - _MARGIN}")
        win.deiconify()
        win.lift()

        win.after(4000, lambda: _safe_destroy(win))

    # --- Queue pollen ---
    def _poll() -> None:
        while True:
            try:
                msg = _q.get_nowait()
            except queue.Empty:
                break
            kind = msg[0]
            if kind == "rec":
                if msg[1]:
                    _show_rec()
                else:
                    rec.withdraw()
            elif kind == "notify":
                _show_notification(msg[1], msg[2])

        root.after(50, _poll)

    root.after(50, _poll)
    root.mainloop()


def _safe_destroy(win: tk.Toplevel) -> None:
    try:
        win.destroy()
    except Exception:
        pass
