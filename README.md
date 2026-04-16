# Blitztext – Sprache zu Text

Blitztext ist ein kleines Programm für Windows, das im Hintergrund läuft und per Tastenkürzel eine Sprachaufnahme startet. Was du sagst, wird automatisch in Text umgewandelt und direkt in das Programm eingefügt, in dem du gerade arbeitest – zum Beispiel Word, Outlook oder ein Browser-Textfeld.

---

## Was du brauchst

- Windows 10 oder Windows 11
- Ein Mikrofon (eingebaut oder extern)
- Internetverbindung (nur für die Installation)

Python und Git werden beim ersten Start automatisch erkannt. Falls sie noch nicht installiert sind, zeigt das Installationsskript, wo du sie herbekommst.

---

## Installation

1. Lade die Datei **`install.bat`** herunter – du bekommst sie von der Person, die dir Blitztext empfohlen hat, oder direkt von [github.com/georg-doenges/Blitztext](https://github.com/georg-doenges/Blitztext).
2. **Doppelklick** auf `install.bat`.
3. Ein schwarzes Fenster öffnet sich kurz, dann startet das Installationsprogramm.
4. Folge den Anweisungen auf dem Bildschirm. Die Installation dauert ein paar Minuten.
5. Am Ende kannst du wählen, ob Blitztext automatisch beim Start von Windows geöffnet werden soll.

Nach der Installation liegt eine Verknüpfung **„Blitztext"** auf deinem Desktop.

### Falls Python oder Git fehlen

Das Installationsskript prüft beides automatisch. Wenn etwas fehlt, bekommst du einen direkten Link zum Download. Wichtig beim Installieren von Python: den Haken bei **„Add Python to PATH"** setzen:

```
[✓] Add Python to PATH
```

---

## Benutzung

### Starten

Doppelklick auf **„Blitztext"** auf dem Desktop. Das Programm erscheint als kleines Symbol in der **Taskleiste unten rechts** (neben der Uhr). Ein Konsolenfenster öffnet sich nicht.

### Aufnahme starten und stoppen

| Aktion | Tastenkürzel |
|---|---|
| Aufnahme starten | **Strg + Umschalt + Leertaste** |
| Aufnahme stoppen | **Strg + Umschalt + Leertaste** (nochmal) |

Der Text erscheint danach automatisch dort, wo du zuletzt getippt hast.

### Das Symbol in der Taskleiste

Das Symbol zeigt an, was Blitztext gerade macht:

| Farbe | Bedeutung |
|---|---|
| **Grau** | Bereit – wartet auf den Hotkey |
| **Rot** | Nimmt auf |
| **Blau** | Verarbeitet die Aufnahme |

Rechtsklick auf das Symbol öffnet ein Menü mit weiteren Optionen.

---

## Die Modi

Blitztext hat drei Arbeitsmodi, wählbar in den Einstellungen oder per Schnellwechsel im Tray-Menü.

**Direkt** (Standard)
Deine Worte werden ohne Änderungen in Text umgewandelt und eingefügt. Schnell, funktioniert komplett offline ohne Internet.

**Poliert – Konservativ** (optional, erfordert Claude-API-Key)
Eine KI überarbeitet den Text minimal: Füllwörter werden entfernt („ähm", „also", „sozusagen"), offensichtliche Grammatikfehler und Wortwiederholungen werden korrigiert. Dein Stil, deine Wortwahl und deine Satzstruktur bleiben erhalten. Gut für alltägliche Texte, Notizen, kurze Nachrichten.

**Poliert – Ausgefeilt** (optional, erfordert Claude-API-Key)
Der Text wird vollständig überarbeitet: saubere Formulierungen, korrekte Zeichensetzung, sinnvolle Absätze. E-Mails werden automatisch korrekt formatiert – Anrede, Fließtext und Grußzeile werden sauber abgesetzt. Gut für formelle Texte und E-Mails.

Schnellwechsel: Rechtsklick auf das Tray-Symbol → **„zu Poliert wechseln"** (wechselt zwischen Direkt und Poliert – Konservativ). Für den Ausgefeilt-Modus einmal in die Einstellungen gehen.

---

## Einstellungen

Rechtsklick auf das Tray-Symbol → **„Einstellungen …"**

| Einstellung | Beschreibung |
|---|---|
| Hotkey | Tastenkürzel ändern (Standard: Strg+Umschalt+Leertaste) |
| Sprache | Sprache der Aufnahme (Standard: Deutsch) |
| Whisper-Modell | Genauigkeit vs. Geschwindigkeit (Standard: small) |
| Claude API Key | Nötig für die Poliert-Modi (Konservativ und Ausgefeilt) |
| Autostart | Beim Windows-Start automatisch starten |

---

## Claude API Key (für die Poliert-Modi)

Den Poliert-Modus brauchst du nicht, wenn dir der Direkt-Modus reicht. Falls du ihn nutzen möchtest:

1. Gehe auf [console.anthropic.com](https://console.anthropic.com) und erstelle ein Konto.
2. Erstelle einen API Key.
3. Trage ihn in den Einstellungen von Blitztext ein.

---

## Häufige Fragen

**Das Symbol erscheint nicht in der Taskleiste.**
Klicke auf den kleinen Pfeil `^` neben der Uhr – das Symbol könnte dort versteckt sein. Du kannst es per Drag & Drop dauerhaft sichtbar machen.

**Der Text wird nicht eingefügt.**
Klicke einmal in das Textfeld, bevor du den Hotkey drückst, damit das richtige Fenster aktiv ist.

**Blitztext reagiert nicht sofort nach dem Start.**
Das Spracherkennungs-Modell wird beim ersten Start geladen – das dauert einen Moment. Sobald es bereit ist, erscheint eine kleine Benachrichtigung: *„Whisper bereit – Hotkey aktiv."*

**In der Eingabeaufforderung (cmd) funktioniert das Einfügen nicht.**
Das ist eine bekannte Einschränkung. In normalen Programmen wie Word, Outlook oder dem Browser funktioniert alles problemlos.

---

## Deinstallation

1. Den Ordner `Blitztext` im Benutzerverzeichnis löschen (`C:\Users\DeinName\Blitztext`).
2. Die Verknüpfung auf dem Desktop löschen.
3. Falls Autostart eingerichtet: `shell:startup` im Explorer öffnen und die Blitztext-Verknüpfung dort löschen.
