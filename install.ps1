# Blitztext - Installer
# Laedt Blitztext von GitHub, richtet die Umgebung ein und erstellt eine Desktop-Verkuepfung.
# Ausfuehren mit: Rechtsklick -> "Mit PowerShell ausfuehren"

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\Blitztext"
)

$ErrorActionPreference = "Stop"
$GITHUB_URL = "https://github.com/georg-doenges/Blitztext.git"
$PYTHON_MIN  = [version]"3.10"
$PYTHON_MAX  = [version]"3.14"   # exklusiv – 3.14 wird von PyTorch/Whisper-Abhaengigkeiten noch nicht durchgaengig unterstuetzt

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "`n    [FEHLER] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  =====================================" -ForegroundColor Cyan
Write-Host "    Blitztext Installer" -ForegroundColor Cyan
Write-Host "  =====================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------------------
# 1. Python pruefen
# -----------------------------------------------------------------------
Write-Step "Python wird geprueft ..."
$python = $null
foreach ($cmd in @("python", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+\.\d+)") {
            $v = [version]$Matches[1]
            if ($v -ge $PYTHON_MIN -and $v -lt $PYTHON_MAX) {
                $python = $cmd
                Write-OK "Gefunden: $ver"
                break
            }
        }
    } catch {}
}
if (-not $python) {
    Write-Fail "Python 3.10 - 3.13 wurde nicht gefunden."
    Write-Warn "Bitte Python installieren: https://www.python.org/downloads/"
    Write-Warn "Wichtig: Haken bei 'Add Python to PATH' setzen!"
    Write-Warn "Achtung: Der Standard-Download auf python.org bietet evtl. bereits Python 3.14"
    Write-Warn "an - das wird von Blitztext noch nicht unterstuetzt. Auf der Downloadseite"
    Write-Warn "unter 'Looking for a specific release?' gezielt eine Python-3.13-Version waehlen."
    Read-Host "`nDruecke Enter zum Beenden"
    exit 1
}

# -----------------------------------------------------------------------
# 2. Git pruefen
# -----------------------------------------------------------------------
Write-Step "Git wird geprueft ..."
try {
    $gitVer = git --version 2>&1
    Write-OK "$gitVer"
} catch {
    Write-Fail "Git wurde nicht gefunden."
    Write-Warn "Bitte Git installieren: https://git-scm.com/download/win"
    Read-Host "`nDruecke Enter zum Beenden"
    exit 1
}

# -----------------------------------------------------------------------
# 3. Repo klonen oder aktualisieren
# -----------------------------------------------------------------------
Write-Step "Blitztext wird von GitHub geladen ..."
if (Test-Path "$InstallDir\.git") {
    Write-Warn "Vorhandene Installation gefunden - wird auf neueste Version aktualisiert ..."
    Push-Location $InstallDir
    git pull origin main
    Pop-Location
} elseif (Test-Path $InstallDir) {
    Write-Warn "Ordner vorhanden aber kein Git-Repository - wird neu geklont ..."
    Remove-Item -Recurse -Force $InstallDir
    git clone $GITHUB_URL $InstallDir
} else {
    git clone $GITHUB_URL $InstallDir
}
Write-OK "Programmdateien bereit in: $InstallDir"

# -----------------------------------------------------------------------
# 4. Virtuelle Python-Umgebung erstellen
# -----------------------------------------------------------------------
Write-Step "Virtuelle Python-Umgebung wird erstellt ..."
$venvDir     = "$InstallDir\.venv"
$venvPython  = "$venvDir\Scripts\python.exe"
$venvPythonW = "$venvDir\Scripts\pythonw.exe"
$venvPip     = "$venvDir\Scripts\pip.exe"

if (-not (Test-Path $venvDir)) {
    & $python -m venv $venvDir
    Write-OK "Umgebung erstellt"
} else {
    Write-OK "Umgebung gefunden - wird geprueft ..."
}

# Venv-Integritaet pruefen: python.exe und pip.exe muessen vorhanden sein
if (-not (Test-Path $venvPython) -or -not (Test-Path $venvPip)) {
    Write-Warn "Venv ist unvollstaendig (fehlende python.exe oder pip.exe) – wird neu erstellt ..."
    Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
    & $python -m venv $venvDir
    if (-not (Test-Path $venvPython)) {
        Write-Fail "Virtuelle Umgebung konnte nicht erstellt werden."
        Write-Warn "Stellen Sie sicher, dass Python korrekt installiert ist."
        Read-Host "`nDruecke Enter zum Beenden"
        exit 1
    }
    Write-OK "Umgebung neu erstellt"
}

# pip aktualisieren
& $venvPython -m pip install --upgrade pip --quiet

# -----------------------------------------------------------------------
# 5. Grafikkarte erkennen und PyTorch installieren
# -----------------------------------------------------------------------
Write-Step "Grafikkarte wird erkannt ..."
$hasNvidia = $false
try {
    $gpu = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" }
    if ($gpu) {
        $hasNvidia = $true
        Write-OK "NVIDIA-GPU gefunden: $($gpu.Name)"
    } else {
        Write-OK "Keine NVIDIA-GPU gefunden - CPU-Modus wird verwendet"
    }
} catch {
    Write-Warn "GPU-Erkennung fehlgeschlagen - installiere CPU-Version"
}

if ($hasNvidia) {
    Write-Warn "Installiere PyTorch mit CUDA-Unterstuetzung (ca. 2-4 GB Download, dauert einige Minuten) ..."
    & $venvPip install torch --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir --timeout 300 --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "PyTorch-Installation fehlgeschlagen (Exitcode $LASTEXITCODE)."
        Write-Warn "Moegliche Ursache: Zu wenig Speicherplatz (benoetigt ca. 5 GB frei)."
        Read-Host "`nDruecke Enter zum Beenden"
        exit 1
    }
    Write-OK "PyTorch mit CUDA-Unterstuetzung installiert"
} else {
    Write-Warn "Installiere PyTorch CPU-Version ..."
    & $venvPip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --timeout 300 --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "PyTorch-Installation fehlgeschlagen (Exitcode $LASTEXITCODE)."
        Write-Warn "Moegliche Ursache: Zu wenig Speicherplatz."
        Read-Host "`nDruecke Enter zum Beenden"
        exit 1
    }
    Write-OK "PyTorch (CPU) installiert"
}

# Sicherstellen dass CUDA_VISIBLE_DEVICES nicht gesetzt ist (koennte GPU blockieren)
[Environment]::SetEnvironmentVariable("CUDA_VISIBLE_DEVICES", $null, "User")

# -----------------------------------------------------------------------
# 6. Weitere Abhaengigkeiten installieren
# -----------------------------------------------------------------------
Write-Step "Weitere Pakete werden installiert ..."
& $venvPip install -r "$InstallDir\requirements.txt" --timeout 300 --no-cache-dir --quiet
Write-OK "Alle Pakete installiert"

# -----------------------------------------------------------------------
# 6c. whisper_device in settings.json eintragen
# -----------------------------------------------------------------------
$settingsDir  = "$env:APPDATA\Blitztext"
$settingsFile = "$settingsDir\settings.json"

$whisperModel = if ($hasNvidia) { "medium" } else { "small" }

New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
if (Test-Path $settingsFile) {
    $json = Get-Content $settingsFile -Raw | ConvertFrom-Json
    $json | Add-Member -NotePropertyName "whisper_device" -NotePropertyValue "auto" -Force
    $json | Add-Member -NotePropertyName "whisper_model"  -NotePropertyValue $whisperModel -Force
    $json | ConvertTo-Json | Set-Content $settingsFile -Encoding UTF8
} else {
    @{ whisper_device = "auto"; whisper_model = $whisperModel } | ConvertTo-Json | Set-Content $settingsFile -Encoding UTF8
}
Write-OK "Whisper-Geraet: auto (GPU wenn vorhanden, sonst CPU)"
Write-OK "Whisper-Modell: $whisperModel"

# -----------------------------------------------------------------------
# 7. Desktop-Verkuepfung erstellen
# -----------------------------------------------------------------------
Write-Step "Desktop-Verkuepfung wird erstellt ..."

# .lnk direkt auf pythonw.exe (kein Konsolenfenster, kein VBS noetig)
$desktopPath  = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\Blitztext.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $venvPythonW
$shortcut.Arguments        = "`"$InstallDir\main.py`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description      = "Blitztext - Sprache zu Text"
$iconPath = "$InstallDir\assets\blitztext.ico"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()
Write-OK "Verkuepfung 'Blitztext' auf dem Desktop erstellt"

# -----------------------------------------------------------------------
# 8. Autostart (optional)
# -----------------------------------------------------------------------
Write-Host ""
$autostart = Read-Host "Soll Blitztext automatisch beim Windows-Start laufen? (j/n)"
if ($autostart -eq "j" -or $autostart -eq "J") {
    # Registry-Eintrag setzen (gleicher Mechanismus wie die Autostart-Checkbox
    # in den Einstellungen) statt einer zusaetzlichen Verknuepfung im
    # Startup-Ordner - sonst gibt es zwei unabhaengige Autostart-Wege.
    Push-Location $InstallDir
    & $venvPython -c "from blitztext import autostart; autostart.enable(r'$InstallDir\main.py')"
    Pop-Location
    Write-OK "Autostart eingerichtet (Registry)"
}

# -----------------------------------------------------------------------
# Abschluss
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "  =============================================" -ForegroundColor Green
Write-Host "    Blitztext wurde erfolgreich installiert!" -ForegroundColor Green
Write-Host "  =============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Starten:      Doppelklick auf 'Blitztext' auf dem Desktop" -ForegroundColor White
Write-Host "  Aufnahme:     Strg + Umschalt + Leertaste (nochmal druecken zum Stoppen)" -ForegroundColor White
Write-Host "  Einstellungen: Strg + Umschalt + Minus" -ForegroundColor White
Write-Host ""
Read-Host "Druecke Enter zum Beenden"
