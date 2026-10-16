@echo off
chcp 65001 > nul
rem デスクトップに bat のショートカットを作る（一度だけ実行）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shortcut.ps1" -Src "%~dp0."
pause
