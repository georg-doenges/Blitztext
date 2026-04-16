@echo off
chcp 65001 >nul
echo.
echo  =====================================
echo    Blitztext - Installation startet
echo  =====================================
echo.
echo  Ein Moment bitte ...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -Command "irm 'https://raw.githubusercontent.com/georg-doenges/Blitztext/main/install.ps1' -OutFile (Join-Path $env:TEMP 'blitztext_install.ps1')"

if %ERRORLEVEL% neq 0 (
    echo.
    echo  [FEHLER] Download fehlgeschlagen.
    echo  Bitte pruefen, ob eine Internetverbindung besteht.
    echo  Ausserdem pruefen: Ist das Repo auf GitHub oeffentlich?
    echo.
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%TEMP%\blitztext_install.ps1"
