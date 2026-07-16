@echo off
REM Run from CMD or double-click — avoids Notepad opening .ps1 files
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-mobile.ps1" %*
