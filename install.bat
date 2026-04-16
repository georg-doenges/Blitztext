@echo off
chcp 65001 >nul
echo.
echo  =====================================
echo    Blitztext – Installation startet
echo  =====================================
echo.
echo  Ein Moment bitte ...
echo.
powershell -ExecutionPolicy Bypass -Command "$f = Join-Path $env:TEMP 'blitztext_install.ps1'; try { irm 'https://raw.githubusercontent.com/georg-doenges/Blitztext/main/install.ps1' -OutFile $f } catch { Write-Host ''; Write-Host '  [FEHLER] Download fehlgeschlagen.' -ForegroundColor Red; Write-Host '  Bitte pruefen, ob eine Internetverbindung besteht.' -ForegroundColor Yellow; Read-Host ''; exit 1 }; & $f"
