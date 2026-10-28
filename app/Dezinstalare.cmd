@echo off
rem Scoate PDF Sign: programul, scurtaturile si intrarile din meniul PDF. Semnaturile raman.
rem Din alt folder: dezinstalarea poate sterge chiar folderul in care sta fisierul asta.
cd /d "%TEMP%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall
pause
