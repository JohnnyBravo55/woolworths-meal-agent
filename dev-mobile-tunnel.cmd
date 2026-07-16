@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-mobile.ps1" -Tunnel %*
