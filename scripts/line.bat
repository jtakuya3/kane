@echo off
chcp 65001 > nul
cd /d %~dp0..
set PY=python
where py > nul 2>&1 && set PY=py -3.11
rem 乖離ラインを計算：line.bat 4498 3909 6721 のように銘柄コードを付けて実行
if "%~1"=="" (
  %PY% -m kane.line_watch
) else (
  %PY% -m kane.line %*
)
pause
