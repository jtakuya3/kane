@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 通知の答え合わせ（記録がたまったら。evaluate.bat 20261016 のように日付を付けるとその日だけ）
if "%~1"=="" (
  %PY% -m kane.evaluate --all
) else (
  %PY% -m kane.evaluate --date %1
)
pause
