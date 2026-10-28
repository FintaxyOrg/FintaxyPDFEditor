@echo off
rem Instaleaza PDF Sign pentru utilizatorul curent: scurtaturi, "Deschide cu" si clic dreapta pe PDF.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
