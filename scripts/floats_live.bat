@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 60秒ごとに latest.html を更新し続ける（止めるときは Ctrl+C）
%PY% -m kane.floats --live --every 60
pause
