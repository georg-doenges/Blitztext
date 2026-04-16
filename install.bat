@echo off
chcp 65001 >nul
echo.
echo  =====================================
echo    Blitztext – Installation startet
echo  =====================================
echo.
echo  Ein Moment bitte ...
echo.
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/georg-doenges/Blitztext/main/install.ps1' -OutFile $env:TEMP\blitztext_install.ps1; & $env:TEMP\blitztext_install.ps1"
