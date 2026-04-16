@echo off
chcp 65001 >nul
echo.
echo  =====================================
echo    Blitztext - Installation startet
echo  =====================================
echo.
echo  Ein Moment bitte ...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -Command "Invoke-WebRequest 'https://raw.githubusercontent.com/georg-doenges/Blitztext/main/install.ps1' -OutFile (Join-Path $env:TEMP 'blitztext_install.ps1') -UseBasicParsing"

if %ERRORLEVEL% neq 0 (
    echo.
    echo  [FEHLER] Download fehlgeschlagen.
    echo  Bitte pruefen, ob eine Internetverbindung besteht.
    echo.
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -Command "$p = Join-Path $env:TEMP 'blitztext_install.ps1'; [IO.File]::WriteAllText($p, [IO.File]::ReadAllText($p), [Text.UTF8Encoding]::new($true))"

powershell -ExecutionPolicy Bypass -NoProfile -File "%TEMP%\blitztext_install.ps1"

pause
